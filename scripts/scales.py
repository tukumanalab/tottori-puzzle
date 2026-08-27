#!/usr/bin/env python3
"""パズルの縮尺・高さ倍率の定義。gen_stl.py と gen_frame.py で共有する。

平面（XY）と地形の起伏は縮尺に比例して小さくなるが、印刷のための物理寸法
（ベース厚さ 3mm・枠厚さ 4mm・ポケット深さ 2mm・クリアランス 0.3mm・
境界リッジ 0.5mm・裏面の文字サイズ）は全縮尺で共通にしている。
そのためどの縮尺でもピースと枠の嵌合は同じで、文字も同じ読みやすさになる。
"""

# 投影中心（全縮尺共通）
PROJ_CENTER_LAT = 35.35
PROJ_CENTER_LON = 133.83
METERS_PER_DEGREE = 111320.0

BASE_XY_SCALE = 1.5 / 450   # 1/300,000（基準）

SCALES = {
    '300k': dict(
        label='1/300,000',
        note='等倍',
        xy_scale=BASE_XY_SCALE,
        dec_mult=1,      # メッシュのセル寸法をモデル座標で一定に保つ
        px_size=0.5,     # 枠のラスタ解像度 (mm/px)。縮尺ほどには細かくしない
                         # （細かくすると小縮尺の方が三角形数が多くなるため）
        sections=('seibu', 'chubu', 'tobu'),
    ),
    '600k': dict(
        label='1/600,000',
        note='1/2',
        xy_scale=BASE_XY_SCALE / 2,
        dec_mult=2,
        px_size=0.4,
        sections=('all',),
    ),
    '900k': dict(
        label='1/900,000',
        note='1/3',
        xy_scale=BASE_XY_SCALE / 3,
        dec_mult=3,
        px_size=0.35,
        sections=('all',),
    ),
}

DEFAULT_SCALE = '300k'

# ── 高さ（Z 方向）の倍率 ────────────────────────────────────────────────────
# 実寸に対する倍率。地形の起伏だけに掛かり、ベース厚さ 3mm には掛からない。
# 枠は境界データだけから作るため、この値の影響を受けない。
# 等倍縮尺で大山 1,729m → 約 17mm の起伏になる。
Z_SCALE = 3.0


def parse_scale_arg(args):
    """引数から --scale を取り出し、(縮尺キーのリスト, 残りの引数) を返す。"""
    keys, rest, i = [], [], 0
    while i < len(args):
        if args[i] == '--scale' and i + 1 < len(args):
            for k in args[i+1].split(','):
                k = k.strip()
                if k == 'all':
                    keys.extend(SCALES)
                elif k in SCALES:
                    keys.append(k)
                else:
                    raise SystemExit(f'不明な縮尺: {k}  (有効: {", ".join(SCALES)}, all)')
            i += 2
        else:
            rest.append(args[i]); i += 1
    return (keys or list(SCALES)), rest
