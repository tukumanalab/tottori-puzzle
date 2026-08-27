#!/usr/bin/env python3
"""
鳥取県市町村の STL ファイルを生成するスクリプト。
public/data/boundary/{code}.json の境界データと国土地理院 DEM を使用。
public/data/stl/{code}.stl に出力する。

Usage:
  python3 scripts/gen_stl.py              # 全市町村
  python3 scripts/gen_stl.py 31201        # 鳥取市のみ
  python3 scripts/gen_stl.py --dec 6 31201

Usage:
  python3 scripts/gen_stl.py --scale 600k          # 1/600,000 のみ
  python3 scripts/gen_stl.py --scale 300k 31201    # 縮尺と市町村を指定

  python3 scripts/gen_stl.py --height z30          # 高さ 3 倍のみ

縮尺:       scripts/scales.py の SCALES 参照（1/300,000 / 1/600,000 / 1/900,000）
縦方向倍率: scripts/scales.py の HEIGHTS 参照（実寸の 1.5 / 2 / 3 倍）
            起伏だけに掛かり、ベース厚さ 3mm には掛からない
裏面: 市町村名のみ（コードなし）
"""
import json, math, os, struct, sys, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np
from scales import (SCALES, HEIGHTS, parse_scale_arg, parse_height_arg,
                    PROJ_CENTER_LAT, PROJ_CENTER_LON, METERS_PER_DEGREE)

# ── 定数 ──────────────────────────────────────────────────────────────────
COS_CENTER = math.cos(PROJ_CENTER_LAT * math.pi / 180)
TILE_SIZE = 256
DEM_TILE_URL = 'https://cyberjapandata.gsi.go.jp/xyz/dem/{z}/{x}/{y}.txt'

# 鳥取県の範囲（離島・沖合の岩礁を除外するフィルタ用）
PREF_BBOX = dict(minLon=132.90, maxLon=134.70, minLat=34.90, maxLat=35.80)

# デフォルトパラメータ
ZOOM       = 13          # zoom13 で約 15m 解像度
# 縦方向倍率は scripts/scales.py の HEIGHTS で選ぶ（実寸の 1.5 / 2 / 3 倍）
BASE_THICK = 3.0         # ベース厚さ (mm)（全縮尺共通）
DECIMATION = 4           # 等倍で zoom13 × dec4 ≒ 62m グリッド ≒ 0.21mm/セル
# ※ 間引きは縮尺に応じて dec_mult 倍する（モデル座標でのセル寸法を一定に保つ）
CLEARANCE_MM = 0.3       # 境界クリアランス (mm)（枠側の 0.3mm と合わせて 0.6mm の遊び）
BBOX_PAD   = 0.015       # 境界ファイルから bbox を計算する際のパディング（度）

CODES = [
    # 市
    '31201','31202','31203','31204',
    # 岩美郡
    '31302',
    # 八頭郡
    '31325','31328','31329',
    # 東伯郡
    '31364','31370','31371','31372',
    # 西伯郡
    '31384','31386','31389','31390',
    # 日野郡
    '31401','31402','31403',
]

# 面積の大きい市町は間引きを強めてポリゴン数を抑える
MUNICIPALITY_PARAMS = {
    '31201': dict(zoom=12, decimation=4),   # 鳥取市 765km²（県内最大）
    '31401': dict(decimation=6),            # 日南町 341km²
    '31203': dict(decimation=6),            # 倉吉市 272km²
    '31364': dict(decimation=6),            # 三朝町 234km²
    '31328': dict(decimation=6),            # 智頭町 224km²
    '31329': dict(decimation=6),            # 八頭町 207km²
    '31325': dict(decimation=6),            # 若桜町 199km²
    '31386': dict(decimation=6),            # 大山町 189km²
    '31384': dict(decimation=2),            # 日吉津村 4.2km²（県内最小・裏面文字の解像度確保）
}

# ── 彫刻設定 ──────────────────────────────────────────────────────────────
ENGRAVE_DEPTH   = 1.5   # 彫り深さ (mm)
ENGRAVE_TEXT_MM = 8.0   # テキスト行高さ上限 (mm)
ENGRAVE_MIN_MM  = 2.0   # テキスト行高さ下限 (mm)
ENGRAVE_MIN_KEEP = 0.6  # これ未満しか収まらないなら彫刻しない（潰れて読めないため）

# ── タイル座標変換 ─────────────────────────────────────────────────────────
def lon_to_tile_x(lon, z): return int((lon + 180) / 360 * (2**z))
def lat_to_tile_y(lat, z):
    lr = lat * math.pi / 180
    return int((1 - math.log(math.tan(lr) + 1 / math.cos(lr)) / math.pi) / 2 * (2**z))
def tile_to_nw(x, y, z):
    n = 2**z
    lon = x / n * 360 - 180
    lat = math.atan(math.sinh(math.pi * (1 - 2 * y / n))) * 180 / math.pi
    return lon, lat

# ── タイル読み込み ─────────────────────────────────────────────────────────
def parse_dem_txt(text):
    data = np.full(TILE_SIZE * TILE_SIZE, np.nan, dtype=np.float32)
    for r, row in enumerate(text.strip().split('\n')[:TILE_SIZE]):
        for c, v in enumerate(row.split(',')[:TILE_SIZE]):
            v = v.strip()
            if v and v != 'e':
                try: data[r * TILE_SIZE + c] = float(v)
                except ValueError: pass
    return data

def load_tile(z, x, y, dem_dir):
    bin_path = os.path.join(dem_dir, str(z), str(x), f'{y}.bin')
    if os.path.exists(bin_path):
        raw = np.frombuffer(open(bin_path, 'rb').read(), dtype='<f4')
        return raw.copy()
    url = DEM_TILE_URL.format(z=z, x=x, y=y)
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            data = parse_dem_txt(r.read().decode())
        os.makedirs(os.path.dirname(bin_path), exist_ok=True)
        data.astype('<f4').tofile(bin_path)
        return data
    except (urllib.error.HTTPError, Exception):
        return np.full(TILE_SIZE * TILE_SIZE, np.nan, dtype=np.float32)

# ── DEM グリッド取得 ───────────────────────────────────────────────────────
def fetch_dem_grid(bbox, dem_dir, zoom=None):
    z = zoom if zoom is not None else ZOOM
    xm = lon_to_tile_x(bbox['minLon'], z)
    xM = lon_to_tile_x(bbox['maxLon'], z)
    ym = lat_to_tile_y(bbox['maxLat'], z)
    yM = lat_to_tile_y(bbox['minLat'], z)
    nX, nY = xM - xm + 1, yM - ym + 1
    cols, rows = nX * TILE_SIZE, nY * TILE_SIZE
    values = np.full((rows, cols), np.nan, dtype=np.float32)

    tasks = [(tx, ty) for ty in range(ym, yM+1) for tx in range(xm, xM+1)]
    total = len(tasks)
    done = [0]
    def _load(tx, ty):
        tile = load_tile(z, tx, ty, dem_dir).reshape(TILE_SIZE, TILE_SIZE)
        ox, oy = (tx - xm) * TILE_SIZE, (ty - ym) * TILE_SIZE
        return tx, ty, tile, ox, oy
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(_load, tx, ty): (tx, ty) for tx, ty in tasks}
        for fut in as_completed(futs):
            tx, ty, tile, ox, oy = fut.result()
            values[oy:oy+TILE_SIZE, ox:ox+TILE_SIZE] = tile
            done[0] += 1
            print(f'\r  タイル {done[0]}/{total}', end='', flush=True)
    print()

    nw_lon, nw_lat = tile_to_nw(xm, ym, z)
    se_lon, se_lat = tile_to_nw(xM+1, yM+1, z)
    bbox_out = dict(minLon=nw_lon, maxLon=se_lon, minLat=se_lat, maxLat=nw_lat)
    return bbox_out, values

# ── 境界 BBox の動的計算 ─────────────────────────────────────────────────
def compute_bbox(polygons):
    """採用したポリゴンから DEM 取得用 bbox を算出（パディング付き）。"""
    all_lons, all_lats = [], []
    for rings in polygons:
        for pt in rings[0]:
            all_lons.append(pt[0]); all_lats.append(pt[1])
    pad = BBOX_PAD
    return dict(
        minLon=min(all_lons) - pad,
        maxLon=max(all_lons) + pad,
        minLat=min(all_lats) - pad,
        maxLat=max(all_lats) + pad,
    )

# ── ポリゴン面積（Shoelace 法） ────────────────────────────────────────────
def ring_area(ring):
    n = len(ring)
    a = 0.0
    for i in range(n):
        j = (i + 1) % n
        a += ring[i][0] * ring[j][1] - ring[j][0] * ring[i][1]
    return abs(a) / 2.0

# ── 孤立ポリゴン検出 ───────────────────────────────────────────────────────
def find_main_component(candidates, coord_decimals=5):
    from collections import defaultdict
    n = len(candidates)
    if n == 0:
        return set()
    coord_to_polys = defaultdict(list)
    for i, (_, rings) in enumerate(candidates):
        for pt in rings[0]:
            key = (round(pt[0], coord_decimals), round(pt[1], coord_decimals))
            coord_to_polys[key].append(i)
    parent = list(range(n))
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py
    for polys in coord_to_polys.values():
        if len(polys) > 1:
            first = polys[0]
            for other in polys[1:]:
                union(first, other)
    comp_area = defaultdict(float)
    for i, (area, _) in enumerate(candidates):
        comp_area[find(i)] += area
    main_root = max(comp_area, key=comp_area.__getitem__)
    return {i for i in range(n) if find(i) == main_root}

# ── ポリゴン抽出 ──────────────────────────────────────────────────────────
def feature_to_polygons(feature):
    geom = feature['geometry']
    b = PREF_BBOX
    candidates = []
    def add_poly(coords):
        rings = [[(p[0], p[1]) for p in ring] for ring in coords]
        outer = rings[0]
        cx = sum(p[0] for p in outer) / len(outer)
        cy = sum(p[1] for p in outer) / len(outer)
        if cx < b['minLon'] or cx > b['maxLon'] or cy < b['minLat'] or cy > b['maxLat']:
            return
        candidates.append((ring_area(outer), rings))
    if geom['type'] == 'Polygon':
        add_poly(geom['coordinates'])
    elif geom['type'] == 'MultiPolygon':
        for poly in geom['coordinates']:
            add_poly(poly)
    if not candidates:
        return []
    main_idx = find_main_component(candidates)
    excluded = len(candidates) - len(main_idx)
    if excluded:
        print(f'  離島・飛び地除外: {excluded} ポリゴン')
    return [rings for i, (_, rings) in enumerate(candidates) if i in main_idx]

# ── ポリゴン塗りつぶしクリッピング ────────────────────────────────────────
def clip_dem(bbox, values, polygons):
    from PIL import Image, ImageDraw
    rows, cols = values.shape
    lon_step = (bbox['maxLon'] - bbox['minLon']) / cols
    lat_step = (bbox['maxLat'] - bbox['minLat']) / rows
    mask_img = Image.new('L', (cols, rows), 0)
    draw = ImageDraw.Draw(mask_img)
    for poly in polygons:
        outer = poly[0]
        pixels = [
            ((p[0] - bbox['minLon']) / lon_step,
             (bbox['maxLat'] - p[1]) / lat_step)
            for p in outer
        ]
        if len(pixels) >= 3:
            draw.polygon(pixels, fill=255)
    mask = np.array(mask_img) > 0
    return np.where(mask, values, np.nan)

# ── 境界クリアランス ──────────────────────────────────────────────────────
def apply_clearance(clipped, px):
    if px <= 0:
        return clipped
    valid = (~np.isnan(clipped)).astype(np.uint8)
    eroded = valid.copy()
    for _ in range(px):
        eroded &= np.roll(eroded,  1, axis=0)
        eroded &= np.roll(eroded, -1, axis=0)
        eroded &= np.roll(eroded,  1, axis=1)
        eroded &= np.roll(eroded, -1, axis=1)
        eroded[0, :] = 0; eroded[-1, :] = 0
        eroded[:, 0] = 0; eroded[:, -1] = 0
    result = clipped.copy()
    result[eroded == 0] = np.nan
    return result

# ── テキスト彫刻 ──────────────────────────────────────────────────────────
def find_jp_font():
    candidates = [
        '/System/Library/Fonts/AquaKana.ttc',
        '/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc',
        '/System/Library/Fonts/Hiragino Sans GB.ttc',
        '/System/Library/Fonts/Supplemental/AppleGothic.ttf',
        '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None

def make_text_bitmap(text_lines, font_path, px_per_mm, font_size_mm):
    """彫刻テキストのビットマップを生成する（裏面から読めるよう左右ミラー）。"""
    from PIL import Image, ImageDraw, ImageFont
    if font_path is None:
        return None
    font_size = max(8, int(font_size_mm * px_per_mm))
    try:
        font = ImageFont.truetype(font_path, font_size)
    except Exception:
        print('  警告: フォント読み込み失敗。テキスト彫刻スキップ。')
        return None
    dummy = ImageDraw.Draw(Image.new('L', (1, 1)))
    line_boxes = [dummy.textbbox((0, 0), l, font=font) for l in text_lines]
    pad = max(1, font_size // 4)
    img_w = max(b[2] - b[0] for b in line_boxes) + pad * 2
    img_h = sum(b[3] - b[1] for b in line_boxes) + pad * (len(text_lines) + 1)
    img = Image.new('L', (img_w, img_h), 0)
    draw = ImageDraw.Draw(img)
    y = pad
    for line, box in zip(text_lines, line_boxes):
        draw.text((pad - box[0], y - box[1]), line, font=font, fill=255)
        y += (box[3] - box[1]) + pad
    img = img.transpose(Image.FLIP_LEFT_RIGHT)  # 裏面から読めるようミラー
    return np.array(img) > 128


def _box_sums(valid, h, w):
    """valid 内の各 h×w 矩形（左上基準）に含まれる有効ピクセル数を積分画像で求める。"""
    rows, cols = valid.shape
    if h > rows or w > cols:
        return None
    ii = np.zeros((rows + 1, cols + 1), dtype=np.int32)
    np.cumsum(np.cumsum(valid.astype(np.int32), axis=0), axis=1, out=ii[1:, 1:])
    R, C = rows - h + 1, cols - w + 1
    return (ii[h:h+R, w:w+C] - ii[0:R, w:w+C] - ii[h:h+R, 0:C] + ii[0:R, 0:C])


def place_text_mask(values, bitmap):
    """テキストビットマップを有効エリア内に配置する。

    矩形全体が市町村の内側に収まる位置を積分画像で厳密に探し、
    その中で重心に最も近い位置を選ぶ。どこにも収まらない場合は
    有効ピクセルを最も多く覆う位置に置き、欠けを許容する。

    Returns:
        mask : 彫刻マスク
        keep : マスクの残存率（1.0 = 欠けずに収まった）
    """
    rows, cols = values.shape
    valid = ~np.isnan(values)
    if bitmap is None or not valid.any():
        return np.zeros((rows, cols), dtype=bool), 0.0
    h, w = bitmap.shape
    sums = _box_sums(valid, h, w)
    if sums is None:
        return np.zeros((rows, cols), dtype=bool), 0.0

    r_idx, c_idx = np.where(valid)
    cr, cc = r_idx.mean() - h / 2, c_idx.mean() - w / 2   # 重心に置いたときの左上

    fits = sums == h * w
    if fits.any():
        fr, fc = np.where(fits)
    else:
        best = sums.max()
        fr, fc = np.where(sums == best)
    d = (fr - cr) ** 2 + (fc - cc) ** 2
    i = int(np.argmin(d))
    r0, c0 = int(fr[i]), int(fc[i])

    mask = np.zeros((rows, cols), dtype=bool)
    mask[r0:r0+h, c0:c0+w] = bitmap
    total = int(bitmap.sum())
    mask &= valid
    keep = int(mask.sum()) / total if total else 0.0
    return mask, keep


def fit_text_mask(values, text_lines, font_path, px_per_mm,
                  max_mm=ENGRAVE_TEXT_MM, min_mm=ENGRAVE_MIN_MM, steps=8):
    """有効エリアに完全に収まる最大フォントサイズを二分探索する。

    Returns:
        mask : 彫刻マスク
        mm   : 採用した行高さ (mm)
        keep : マスクの残存率（1.0 = 欠けずに収まった）
    """
    def attempt(mm):
        return place_text_mask(values, make_text_bitmap(text_lines, font_path, px_per_mm, mm))

    mask, keep = attempt(max_mm)
    if keep >= 1.0:
        return mask, max_mm, keep

    lo, hi = min_mm, max_mm
    best = None
    for _ in range(steps):
        mid = (lo + hi) / 2
        m, k = attempt(mid)
        if k >= 1.0:
            best = (m, mid, k)
            lo = mid
        else:
            hi = mid
    if best is not None:
        return best
    # どのサイズでも収まらない場合は最小サイズで欠けを許容する
    mask, keep = attempt(min_mm)
    return mask, min_mm, keep



def pool_mask(mask, dec):
    rows, cols = mask.shape
    hpad = (-rows) % dec
    wpad = (-cols) % dec
    if hpad or wpad:
        mask = np.pad(mask, ((0, hpad), (0, wpad)))
    h2, w2 = mask.shape
    return mask.reshape(h2 // dec, dec, w2 // dec, dec).any(axis=(1, 3))

# ワールド座標スケール（gen_one で上書きする）
_CUR_XY_SCALE = SCALES['300k']['xy_scale']
_CUR_Z_SCALE  = HEIGHTS['z15']['z_scale']

# ── ワールド座標グリッド ───────────────────────────────────────────────────
def world_grid(bbox, values):
    rows, cols = values.shape
    lon_step = (bbox['maxLon'] - bbox['minLon']) / cols
    lat_step = (bbox['maxLat'] - bbox['minLat']) / rows
    c_idx = np.arange(cols, dtype=np.float32)
    r_idx = np.arange(rows, dtype=np.float32)
    lons = bbox['minLon'] + (c_idx + 0.5) * lon_step
    lats = bbox['maxLat'] - (r_idx + 0.5) * lat_step
    lons2d, lats2d = np.meshgrid(lons, lats)
    s = _CUR_XY_SCALE
    wx = ((lons2d - PROJ_CENTER_LON) * COS_CENTER * METERS_PER_DEGREE * s).astype(np.float32)
    wy = ((lats2d - PROJ_CENTER_LAT) * METERS_PER_DEGREE * s).astype(np.float32)
    wz = np.where(np.isnan(values), np.nan, (values * _CUR_Z_SCALE * s).astype(np.float32))
    return wx, wy, wz

# ── STL 型 ────────────────────────────────────────────────────────────────
STL_TRI = np.dtype([('n','<3f4'),('v0','<3f4'),('v1','<3f4'),('v2','<3f4'),('a','<u2')])

def _norms(e1, e2):
    n = np.cross(e1, e2)
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    ln = np.where(ln > 0, ln, 1.0)
    return (n / ln).astype(np.float32)

def make_tris(p0, p1, p2):
    e1 = p1 - p0; e2 = p2 - p0
    n = _norms(e1, e2)
    out = np.zeros(len(p0), dtype=STL_TRI)
    out['n'] = n; out['v0'] = p0; out['v1'] = p1; out['v2'] = p2
    return out

# ── セル格子 ──────────────────────────────────────────────────────────────
def cell_grid(values, dec):
    """地形面・底面を張るセル格子を返す。

    セルは 4 隅 (R,C) (R2,C) (R,C2) (R2,C2) からなり、どれか 1 つでも
    標高が有効ならメッシュを張る。側壁・テキスト壁もこの同じセル集合から
    生成することで、上面・底面・側面の外周がぴったり一致し水密になる。

    Returns:
        R, C, R2, C2 : セル 4 隅の行/列インデックス（2 次元配列）
        m            : そのセルにメッシュを張るか（2 次元 bool）
    """
    rows, cols = values.shape
    R, C = np.meshgrid(np.arange(0, rows-dec, dec), np.arange(0, cols-dec, dec), indexing='ij')
    R2 = np.minimum(R + dec, rows-1)
    C2 = np.minimum(C + dec, cols-1)
    m = ~(np.isnan(values[R, C]) & np.isnan(values[R2, C]) &
          np.isnan(values[R, C2]) & np.isnan(values[R2, C2]))
    return R, C, R2, C2, m


def align_mask(mask, shape):
    """pool_mask の出力をセル格子の形に合わせる。"""
    out = np.zeros(shape, dtype=bool)
    if mask is None:
        return out
    h = min(shape[0], mask.shape[0]); w = min(shape[1], mask.shape[1])
    out[:h, :w] = mask[:h, :w]
    return out


def text_cells(values, dec, text_mask):
    """彫刻テキストを載せるセル。外周に接するセルは除外する。

    テキストの窪みが外周まで達すると、側壁の下端（base_z）と底面の段差
    （base_z + ENGRAVE_DEPTH）が噛み合わず穴になる。4 近傍のどれかが欠けて
    いるセルを彫刻対象から外すことで、窪みは必ずピース内部に収まる。
    """
    _, _, _, _, m = cell_grid(values, dec)
    interior = (m & _nbr(m, -1, 0) & _nbr(m, +1, 0)
                  & _nbr(m, 0, -1) & _nbr(m, 0, +1))
    return align_mask(text_mask, m.shape) & interior


def _nbr(mask, di, dj):
    """(di, dj) 方向の隣接セルの値。範囲外は False。"""
    p = np.pad(mask, 1)
    h, w = mask.shape
    return p[1+di:1+di+h, 1+dj:1+dj+w]


# ── 地形メッシュ ──────────────────────────────────────────────────────────
def build_terrain(bbox, values, dec):
    wx, wy, wz = world_grid(bbox, values)
    sea_z = np.float32(0.0)
    wz_f = np.where(np.isnan(wz), sea_z, wz).astype(np.float32)

    valid_z = wz_f[~np.isnan(wz)]
    min_valid_z = float(valid_z.min()) if len(valid_z) else 0.0
    base_z = min(min_valid_z, 0.0) - BASE_THICK

    R, C, R2, C2, m = cell_grid(values, dec)
    R=R[m]; C=C[m]; R2=R2[m]; C2=C2[m]

    def xyz(r, c): return np.stack([wx[r,c], wy[r,c], wz_f[r,c]], axis=1)
    A=xyz(R,C); B=xyz(R2,C); C_=xyz(R,C2); D=xyz(R2,C2)

    # 上面なので +Z 向き（反時計回り）になる巻き順にする
    t1 = make_tris(A, B, C_)
    t2 = make_tris(B, D, C_)
    return np.concatenate([t1, t2]), base_z

# ── 壁メッシュ ────────────────────────────────────────────────────────────
def _wall_quads(x1, y1, z1, x2, y2, z2, bz):
    """p1→p2 の進行方向に対して左側を表（法線の向き）とする壁を生成する。
    呼び出し側は外側が左に来るよう始点・終点を渡すこと。
    bz はスカラーでもセルごとの配列でもよい。"""
    nx = -(y2 - y1); ny = x2 - x1
    ln = np.sqrt(nx**2 + ny**2); ln = np.where(ln > 0, ln, 1.0)
    nx = nx / ln; ny = ny / ln
    nz = np.zeros_like(nx)
    bz_arr = np.broadcast_to(np.asarray(bz, dtype=np.float32), (len(x1),)).astype(np.float32)
    p1t = np.stack([x1, y1, z1], axis=1).astype(np.float32)
    p2t = np.stack([x2, y2, z2], axis=1).astype(np.float32)
    p1b = np.stack([x1, y1, bz_arr], axis=1).astype(np.float32)
    p2b = np.stack([x2, y2, bz_arr], axis=1).astype(np.float32)
    nm  = np.stack([nx, ny, nz], axis=1).astype(np.float32)
    N = len(x1)
    out = np.zeros(N * 2, dtype=STL_TRI)
    out['n'][:N] = nm; out['v0'][:N] = p1t; out['v1'][:N] = p2t; out['v2'][:N] = p1b
    out['n'][N:] = nm; out['v0'][N:] = p2t; out['v1'][N:] = p2b; out['v2'][N:] = p1b
    return out


def build_walls(bbox, values, base_z, dec):
    """メッシュ外周の側壁。地形面と同じセル格子の縁に沿って生成する。

    彫刻セルは外周に接しない（text_cells 参照）ため、下端は常に base_z。
    """
    wx, wy, wz = world_grid(bbox, values)
    wz_f = np.where(np.isnan(wz), np.float32(0.0), wz).astype(np.float32)

    R, C, R2, C2, m = cell_grid(values, dec)

    def edge(sel, r_a, c_a, r_b, c_b):
        """sel が True のセルについて、隅 a→隅 b の辺に壁を張る。"""
        ra, ca = r_a[sel], c_a[sel]
        rb, cb = r_b[sel], c_b[sel]
        return _wall_quads(wx[ra,ca], wy[ra,ca], wz_f[ra,ca],
                           wx[rb,cb], wy[rb,cb], wz_f[rb,cb], np.float32(base_z))

    parts = []
    # 北辺（隣セルなし）: 外向き +y → A→C_
    sel = m & ~_nbr(m, -1, 0)
    if sel.any(): parts.append(edge(sel, R, C, R, C2))
    # 南辺: 外向き -y → D→B
    sel = m & ~_nbr(m, +1, 0)
    if sel.any(): parts.append(edge(sel, R2, C2, R2, C))
    # 西辺: 外向き -x → B→A
    sel = m & ~_nbr(m, 0, -1)
    if sel.any(): parts.append(edge(sel, R2, C, R, C))
    # 東辺: 外向き +x → C_→D
    sel = m & ~_nbr(m, 0, +1)
    if sel.any(): parts.append(edge(sel, R, C2, R2, C2))
    return np.concatenate(parts) if parts else np.zeros(0, dtype=STL_TRI)

# ── 底面メッシュ ──────────────────────────────────────────────────────────
def build_bottom(bbox, values, base_z, dec, text_mask=None):
    wx, wy, _ = world_grid(bbox, values)
    R, C, R2, C2, m = cell_grid(values, dec)
    tm = text_cells(values, dec, text_mask)
    bz_cell = np.where(tm, np.float32(base_z + ENGRAVE_DEPTH), np.float32(base_z))

    Rf=R[m]; Cf=C[m]; R2f=R2[m]; C2f=C2[m]; bz = bz_cell[m].astype(np.float32)

    def xyz_bot(r, c): return np.stack([wx[r,c], wy[r,c], bz], axis=1).astype(np.float32)
    A=xyz_bot(Rf,Cf); B=xyz_bot(R2f,Cf); C_=xyz_bot(Rf,C2f); D=xyz_bot(R2f,C2f)

    # 底面なので -Z 向きになる巻き順にする
    t1 = make_tris(A, C_, B)
    t2 = make_tris(B, C_, D)
    tris = np.concatenate([t1, t2])
    tris['n'] = (0.0, 0.0, -1.0)
    return tris

def build_text_walls(bbox, values, base_z, dec, text_mask):
    """彫刻テキストの段差壁。テキストセルと非テキストセルの境界に立てる。

    隣がメッシュ外のセルの場合は外周の側壁（build_walls）が受け持つため
    ここでは張らない。
    """
    if text_mask is None or not text_mask.any():
        return np.zeros(0, dtype=STL_TRI)
    wx, wy, _ = world_grid(bbox, values)
    R, C, R2, C2, m = cell_grid(values, dec)
    tm = text_cells(values, dec, text_mask)
    if not tm.any():
        return np.zeros(0, dtype=STL_TRI)

    bz_txt = np.float32(base_z + ENGRAVE_DEPTH)
    bz_bg  = np.float32(base_z)

    def edge(sel, r_a, c_a, r_b, c_b):
        ra, ca = r_a[sel], c_a[sel]
        rb, cb = r_b[sel], c_b[sel]
        top = np.full(int(sel.sum()), bz_txt, dtype=np.float32)
        return _wall_quads(wx[ra,ca], wy[ra,ca], top,
                           wx[rb,cb], wy[rb,cb], top, bz_bg)

    parts = []
    # 北隣が非テキスト: 空洞（テキスト側）は南 → 外向き -y → C_→A
    sel = tm & _nbr(m, -1, 0) & ~_nbr(tm, -1, 0)
    if sel.any(): parts.append(edge(sel, R, C2, R, C))
    # 南隣が非テキスト: 外向き +y → B→D
    sel = tm & _nbr(m, +1, 0) & ~_nbr(tm, +1, 0)
    if sel.any(): parts.append(edge(sel, R2, C, R2, C2))
    # 西隣が非テキスト: 外向き +x → A→B
    sel = tm & _nbr(m, 0, -1) & ~_nbr(tm, 0, -1)
    if sel.any(): parts.append(edge(sel, R, C, R2, C))
    # 東隣が非テキスト: 外向き -x → D→C_
    sel = tm & _nbr(m, 0, +1) & ~_nbr(tm, 0, +1)
    if sel.any(): parts.append(edge(sel, R2, C2, R, C2))
    return np.concatenate(parts) if parts else np.zeros(0, dtype=STL_TRI)


# ── STL 書き出し ──────────────────────────────────────────────────────────
def write_stl(path, tri_arrays):
    all_tris = np.concatenate([t for t in tri_arrays if len(t) > 0])
    with open(path, 'wb') as f:
        f.write(b'\x00' * 80)
        f.write(struct.pack('<I', len(all_tris)))
        f.write(all_tris.tobytes())

# ── メイン ────────────────────────────────────────────────────────────────
def gen_one(code, base_dir, dec, scale_key, height_keys):
    """1 市町村を、指定された全ての高さ倍率で生成する。

    DEM の取得・クリッピング・裏面テキストの配置は高さ倍率に依存しないので
    一度だけ行い、メッシュ生成だけを倍率ごとに繰り返す。
    """
    global _CUR_XY_SCALE, _CUR_Z_SCALE
    scale = SCALES[scale_key]
    params = MUNICIPALITY_PARAMS.get(code, {})
    _CUR_XY_SCALE = scale['xy_scale']
    pref_zoom = params.get('zoom', None)
    # 間引きは縮尺に応じて強める（モデル座標でのセル寸法を一定に保つ）
    dec = params.get('decimation', dec) * scale['dec_mult']

    boundary_path = os.path.join(base_dir, 'public', 'data', 'boundary', f'{code}.json')
    dem_dir       = os.path.join(base_dir, 'public', 'data', 'dem')

    print(f'\n=== {code} @ {scale["label"]} ===')
    with open(boundary_path) as f:
        feature = json.load(f)

    name = feature['properties'].get('name', code)
    print(f'  名称: {name}')

    polygons = feature_to_polygons(feature)
    if not polygons:
        print('  警告: 有効なポリゴンがありません。スキップ。')
        return {}
    bbox = compute_bbox(polygons)
    print(f'  bbox: lon {bbox["minLon"]:.4f}–{bbox["maxLon"]:.4f}  lat {bbox["minLat"]:.4f}–{bbox["maxLat"]:.4f}')

    print('  DEM 読み込み中...')
    grid_bbox, values = fetch_dem_grid(bbox, dem_dir, zoom=pref_zoom)
    print(f'  グリッド: {values.shape[0]}×{values.shape[1]}')

    # グリッド 1px あたりのモデル寸法（mm）
    grid_pixel_lon = (grid_bbox['maxLon'] - grid_bbox['minLon']) / values.shape[1]
    grid_pixel_mm  = grid_pixel_lon * COS_CENTER * METERS_PER_DEGREE * _CUR_XY_SCALE
    px_per_mm = 1.0 / grid_pixel_mm

    print('  クリッピング中...')
    clearance_px = max(1, round(CLEARANCE_MM * px_per_mm))
    clipped  = clip_dem(grid_bbox, values, polygons)
    clipped  = apply_clearance(clipped, clearance_px)
    valid_n  = int(np.sum(~np.isnan(clipped)))
    print(f'  クリアランス: {clearance_px} px ({CLEARANCE_MM} mm)')
    print(f'  有効セル: {valid_n:,}')
    if valid_n == 0:
        print('  警告: 有効セルがありません。スキップ。')
        return {}

    print('  テキストマスク生成...')
    jp_font = find_jp_font()

    # 裏面には市町村名のみ印刷（コードなし）
    # 1行・2行どちらが大きく収まるか試す
    cands = [('1行', *fit_text_mask(clipped, [name], jp_font, px_per_mm))]
    # 名称が4文字以上なら2行分割も試みる（例: 「日吉」「津村」）
    if len(name) >= 4:
        mid = len(name) // 2
        cands.append(('2行', *fit_text_mask(clipped, [name[:mid], name[mid:]], jp_font, px_per_mm)))

    # 欠けずに収まったものを優先し、その中で最大サイズを選ぶ
    layout, text_mask, used_mm, keep = max(cands, key=lambda c: (c[3] >= 1.0, c[3], c[2]))
    if keep < ENGRAVE_MIN_KEEP:
        # 潰れて読めない彫刻を入れるくらいなら、無地の裏面にする
        print(f'  テキスト: {keep*100:.0f}% しか収まらないため彫刻しない（ピースが小さすぎる）')
        text_mask = np.zeros_like(text_mask)
        text_mask_pooled = pool_mask(text_mask, dec)
    else:
        warn = '' if keep >= 1.0 else f'  ※ {keep*100:.0f}% しか収まらず'
        print(f'  テキスト: {layout} {used_mm:.1f} mm  ピクセル: {text_mask.sum():,}{warn}')
        text_mask_pooled = pool_mask(text_mask, dec)

    # ── 高さ倍率ごとにメッシュを生成 ──────────────────────────────
    results = {}
    for hk in height_keys:
        _CUR_Z_SCALE = HEIGHTS[hk]['z_scale']
        out_dir  = os.path.join(base_dir, 'public', 'data', 'stl', scale_key, hk)
        out_path = os.path.join(out_dir, f'{code}.stl')

        terrain_tris, base_z = build_terrain(grid_bbox, clipped, dec)
        wall_tris     = build_walls(grid_bbox, clipped, base_z, dec)
        bot_tris      = build_bottom(grid_bbox, clipped, base_z, dec, text_mask_pooled)
        txt_wall_tris = build_text_walls(grid_bbox, clipped, base_z, dec, text_mask_pooled)

        os.makedirs(out_dir, exist_ok=True)
        parts = [terrain_tris, wall_tris, bot_tris, txt_wall_tris]
        write_stl(out_path, parts)
        mb = os.path.getsize(out_path) / (1024**2)
        total = sum(len(t) for t in parts)

        verts = np.concatenate([np.concatenate([t['v0'], t['v1'], t['v2']])
                                for t in parts if len(t)])
        lo = verts.min(axis=0); hi = verts.max(axis=0)
        results[hk] = dict(code=code, name=name,
                           w=round(float(hi[0] - lo[0]), 1),
                           h=round(float(hi[1] - lo[1]), 1),
                           z=round(float(hi[2] - lo[2]), 1),
                           tri=int(total), mb=round(mb, 1))
        print(f'  高さ{HEIGHTS[hk]["label"]}: 起伏 {hi[2]:.1f} mm / 全高 {results[hk]["z"]:.1f} mm'
              f'  → {os.path.relpath(out_path, base_dir)}  ({total:,} tri, {mb:.1f} MB)')
    return results

def main():
    scale_keys, args = parse_scale_arg(sys.argv[1:])
    height_keys, args = parse_height_arg(args)
    dec = DECIMATION
    codes = []
    i = 0
    while i < len(args):
        if args[i] == '--dec' and i + 1 < len(args):
            dec = int(args[i+1]); i += 2
        else:
            codes.append(args[i]); i += 1
    if not codes:
        codes = CODES

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    manifest_path = os.path.join(base_dir, 'public', 'data', 'pieces.json')
    manifest = {}
    if os.path.exists(manifest_path):
        with open(manifest_path) as f:
            manifest = json.load(f)

    heights_desc = ' / '.join(HEIGHTS[h]['label'] for h in height_keys)
    for scale_key in scale_keys:
        sc = SCALES[scale_key]
        print(f'\n########## 縮尺 {sc["label"]}（{sc["note"]}）  高さ {heights_desc}  '
              f'decimation={dec}×{sc["dec_mult"]}  zoom={ZOOM} ##########')
        by_height = manifest.get(scale_key, {})
        for code in codes:
            for hk, info in gen_one(code, base_dir, dec, scale_key, height_keys).items():
                by_height.setdefault(hk, {})[code] = info
        manifest[scale_key] = by_height

    # 縮尺・高さ・市町村コードの並びを定義順に揃える
    ordered = {
        sk: {hk: {c: manifest[sk][hk][c] for c in CODES if c in manifest[sk][hk]}
             for hk in HEIGHTS if hk in manifest[sk]}
        for sk in SCALES if sk in manifest
    }
    os.makedirs(os.path.dirname(manifest_path), exist_ok=True)
    with open(manifest_path, 'w') as f:
        json.dump(ordered, f, ensure_ascii=False, indent=1)
    print(f'\nマニフェスト: {manifest_path}')
    print('\n全完了。')

if __name__ == '__main__':
    main()
