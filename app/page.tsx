'use client';
import { useEffect, useState } from 'react';
import dynamic from 'next/dynamic';
import { SEIBU, CHUBU, TOBU, SCALES, DEFAULT_SCALE, Z_SCALE_LABEL, BASE_PATH } from '../lib/constants/tottori';
import type { MunicipalityInfo, PieceManifest, FrameManifest } from '../lib/types';

const StlViewer = dynamic(() => import('./components/StlViewer'), { ssr: false });

const GROUPS = [
  { label: '西部（米子市・境港市・西伯郡・日野郡）', zipName: 'seibu', municipalities: SEIBU },
  { label: '中部（倉吉市・東伯郡）',                 zipName: 'chubu', municipalities: CHUBU },
  { label: '東部（鳥取市・岩美郡・八頭郡）',         zipName: 'tobu',  municipalities: TOBU },
];

const README_TXT = (scaleLabel: string) =>
  `鳥取県 3D 市町村パズル（縮尺 ${scaleLabel} / 高さ ${Z_SCALE_LABEL}）\n\n` +
  '地形データ: 国土地理院 基盤地図情報数値標高モデル（DEM）\n' +
  '行政界データ: 国土交通省 国土数値情報（行政区域データ）N03-2024\n' +
  '本データは上記データを加工して作成したものです。\n';

const mm = (v: number) => (v >= 10 ? v.toFixed(0) : v.toFixed(1));
const no2 = (n: number) => String(n).padStart(2, '0');
const pieceFileName = (m: MunicipalityInfo, scale: string) =>
  `${no2(m.no)}_${m.code}_${m.nameEn}_${scale}.stl`;

export default function HomePage() {
  const [scale, setScale] = useState(DEFAULT_SCALE);
  const [pieces, setPieces] = useState<PieceManifest>({});
  const [frames, setFrames] = useState<FrameManifest>({});
  const [zippingKey, setZippingKey] = useState<string | null>(null);
  const [preview, setPreview] = useState<{ path: string; name: string; color: string } | null>(null);
  const [openGroups, setOpenGroups] = useState<Set<string>>(new Set(GROUPS.map(g => g.label)));
  const [excluded, setExcluded] = useState<Set<string>>(new Set());

  useEffect(() => {
    fetch(`${BASE_PATH}/data/pieces.json`).then(r => r.ok ? r.json() : {}).then(setPieces).catch(() => {});
    fetch(`${BASE_PATH}/data/frames.json`).then(r => r.ok ? r.json() : {}).then(setFrames).catch(() => {});
  }, []);

  const scaleInfo = SCALES.find(s => s.key === scale)!;
  const pieceInfo = pieces[scale] ?? {};
  const frameInfo = frames[scale];
  const stlUrl = (file: string) => `${BASE_PATH}/data/stl/${scale}/${file}`;

  function toggleExclude(code: string) {
    setExcluded(prev => {
      const next = new Set(prev);
      next.has(code) ? next.delete(code) : next.add(code);
      return next;
    });
  }

  function toggleGroup(label: string) {
    setOpenGroups(prev => {
      const next = new Set(prev);
      next.has(label) ? next.delete(label) : next.add(label);
      return next;
    });
  }

  async function buildAndDownloadZip(municipalities: MunicipalityInfo[], name: string, key: string) {
    setZippingKey(key);
    try {
      const JSZip = (await import('jszip')).default;
      const zip = new JSZip();
      const targets = municipalities.filter(m => !excluded.has(m.code));
      await Promise.all(targets.map(async (m) => {
        const resp = await fetch(stlUrl(`${m.code}.stl`));
        if (resp.ok) zip.file(pieceFileName(m, scale), await resp.arrayBuffer());
      }));
      zip.file('README.txt', README_TXT(scaleInfo.label));
      const blob = await zip.generateAsync({ type: 'blob' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = `tottori-puzzle-${name}-${scale}.zip`; a.click();
      URL.revokeObjectURL(url);
    } finally {
      setZippingKey(null);
    }
  }

  return (
    <>
      <div className="max-w-xl mx-auto px-4 py-12 flex flex-col gap-10">

        <header className="flex flex-col gap-2">
          <h1 className="text-3xl font-bold tracking-tight">鳥取県 3D 市町村パズル</h1>
          <p className="text-gray-400 leading-relaxed">
            鳥取県の市町村（19 市町村）の地形を 3D プリントできるパズルです。<br />
            国土地理院の標高データから生成した STL ファイルを配布しています。
          </p>
        </header>

        <section className="flex flex-col gap-3">
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-widest border-b border-gray-800 pb-2">
            縮尺
          </h2>
          <div className="grid grid-cols-3 gap-2">
            {SCALES.map((s) => {
              const f = frames[s.key];
              const active = s.key === scale;
              return (
                <button
                  key={s.key}
                  onClick={() => setScale(s.key)}
                  aria-pressed={active}
                  className={`flex flex-col items-center gap-0.5 py-3 px-2 rounded-lg border transition-colors ${
                    active
                      ? 'border-emerald-500 bg-emerald-950/60 text-gray-100'
                      : 'border-gray-800 hover:border-gray-600 text-gray-400'
                  }`}
                >
                  <span className="font-semibold text-sm">{s.label}</span>
                  <span className="text-xs text-gray-500">{s.note}</span>
                  {f && (
                    <span className="text-[11px] text-gray-600 mt-0.5">
                      全体 {mm(f.overall.w)}×{mm(f.overall.h)} mm
                    </span>
                  )}
                </button>
              );
            })}
          </div>
          <p className="text-xs text-gray-500">
            縮尺で変わるのは平面の大きさと地形の起伏だけです。ベース厚さ 3mm・枠厚さ 4mm・
            嵌合のクリアランス 0.3mm・裏面の文字サイズは全縮尺で共通なので、どれを選んでも
            同じように嵌まり、同じ読みやすさになります。<br />
            地形の起伏は{Z_SCALE_LABEL}に強調しています（起伏だけに掛かり、ベース厚さには掛かりません）。
          </p>
          <p className="text-xs text-gray-500">
            市町村名の左の数字は 1〜19 の通し番号です。全国地方公共団体コード順
            （市 4 つ → 岩美郡 → 八頭郡 → 東伯郡 → 西伯郡 → 日野郡）で振っていて、
            ダウンロードするファイル名の先頭にも付きます（例: <code className="text-gray-400">01_31201_Tottori_300k.stl</code>）。
          </p>
        </section>


        {GROUPS.map((group) => {
          const isOpen = openGroups.has(group.label);
          const isZipping = zippingKey === group.label;
          return (
            <section key={group.label} className="flex flex-col">
              <div className="flex items-center justify-between border-b border-gray-800 pb-2">
                <button
                  onClick={() => toggleGroup(group.label)}
                  className="flex items-center gap-2 group flex-1 min-w-0"
                >
                  <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-widest group-hover:text-gray-300 transition-colors truncate">
                    {group.label}
                  </h2>
                  <span className={`text-gray-600 text-xs transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`}>▼</span>
                </button>
                <button
                  onClick={() => buildAndDownloadZip(group.municipalities, group.zipName, group.label)}
                  disabled={isZipping}
                  className="text-xs text-emerald-500 hover:text-emerald-300 disabled:opacity-50 transition-colors flex-shrink-0 ml-4"
                >
                  {isZipping ? 'ZIP 作成中...' : 'ZIP ダウンロード'}
                </button>
              </div>
              {isOpen && (
                <ul className="flex flex-col divide-y divide-gray-800">
                  {group.municipalities.map((m) => {
                    const info = pieceInfo[m.code];
                    return (
                      <li key={m.code} className="flex items-center justify-between py-4 gap-3">
                        <div className="flex items-center gap-2.5 min-w-0">
                          <input
                            type="checkbox"
                            checked={!excluded.has(m.code)}
                            onChange={() => toggleExclude(m.code)}
                            className="w-4 h-4 flex-shrink-0 accent-emerald-500 cursor-pointer"
                          />
                          <span
                            className="text-xs tabular-nums text-gray-500 w-5 text-right flex-shrink-0"
                            title={`通し番号 ${m.no} / 全国地方公共団体コード ${m.code}`}
                          >
                            {m.no}
                          </span>
                          <span className="w-1 h-8 rounded-full flex-shrink-0" style={{ background: m.color }} />
                          <div className={`min-w-0 ${excluded.has(m.code) ? 'opacity-40' : ''}`}>
                            <div className="flex items-baseline gap-2">
                              <span className="font-semibold">{m.name}</span>
                              <span className="text-gray-500 text-sm">{m.nameEn}</span>
                            </div>
                            {info && (
                              <div className="text-xs text-gray-600 whitespace-nowrap">
                                {mm(info.w)} × {mm(info.h)} mm・全高 {info.z.toFixed(1)} mm
                                <span className="text-gray-700">（うち起伏 {(info.z - 3).toFixed(1)} mm）</span>
                              </div>
                            )}
                          </div>
                        </div>
                        <div className="flex items-center gap-4 flex-shrink-0">
                          <button
                            onClick={() => setPreview({ path: `${m.code}.stl`, name: `${m.no}. ${m.name}`, color: m.color })}
                            className="text-sm text-gray-500 hover:text-gray-200 transition-colors"
                          >
                            プレビュー
                          </button>
                          <a
                            href={stlUrl(`${m.code}.stl`)}
                            download={pieceFileName(m, scale)}
                            className="bg-blue-600 hover:bg-blue-500 transition-colors px-3 py-1.5 rounded text-sm font-medium"
                          >
                            ダウンロード
                          </a>
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}
            </section>
          );
        })}

        <button
          onClick={() => buildAndDownloadZip(GROUPS.flatMap(g => g.municipalities), 'all', 'all')}
          disabled={zippingKey === 'all'}
          className="w-full py-3 bg-emerald-700 hover:bg-emerald-600 disabled:opacity-50 transition-colors rounded-lg font-semibold"
        >
          {zippingKey === 'all' ? 'ZIP 作成中...' : '全市町村まとめてダウンロード（ZIP）'}
        </button>

        <section className="flex flex-col gap-3">
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-widest border-b border-gray-800 pb-2">
            枠（フレーム）
          </h2>
          <p className="text-xs text-gray-500">
            {frameInfo && frameInfo.sections.length > 1
              ? `ピースをはめ込むトレイ型の枠です。${frameInfo.sections.length} つのセクションをタブでつなげて一体の枠（全体 ~${mm(frameInfo.overall.w)} × ${mm(frameInfo.overall.h)} mm）として使用できます。`
              : frameInfo
                ? `ピースをはめ込むトレイ型の枠です。この縮尺なら全体（~${mm(frameInfo.overall.w)} × ${mm(frameInfo.overall.h)} mm）が 1 枚に収まるため分割していません。`
                : 'ピースをはめ込むトレイ型の枠です。'}
          </p>
          <div className="flex flex-col gap-2">
            {(frameInfo?.sections ?? []).map((f) => (
              <div key={f.file} className="flex items-center justify-between py-2 border-b border-gray-800 last:border-0 gap-4">
                <div className="min-w-0">
                  <div className="font-medium text-sm truncate">{f.label}</div>
                  <div className="text-gray-500 text-xs">{mm(f.w)} × {mm(f.h)} mm・{f.mb} MB</div>
                </div>
                <div className="flex items-center gap-4 flex-shrink-0">
                  <button
                    onClick={() => setPreview({ path: f.file, name: `枠 — ${f.label}`, color: '#888888' })}
                    className="text-sm text-gray-500 hover:text-gray-200 transition-colors"
                  >
                    プレビュー
                  </button>
                  <a
                    href={stlUrl(f.file)}
                    download={f.file.replace('.stl', `_${scale}.stl`)}
                    className="bg-blue-600 hover:bg-blue-500 transition-colors px-3 py-1.5 rounded text-sm font-medium"
                  >
                    ダウンロード
                  </a>
                </div>
              </div>
            ))}
          </div>
        </section>

        <footer className="text-xs text-gray-600 border-t border-gray-800 pt-5 flex flex-col gap-1">
          <span>地形: <a href="https://maps.gsi.go.jp/development/ichiran.html" className="underline hover:text-gray-400 transition-colors">国土地理院 基盤地図情報数値標高モデル</a></span>
          <span>行政界: <a href="https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-N03-v3_1.html" className="underline hover:text-gray-400 transition-colors">国土交通省 国土数値情報 N03-2024</a></span>
        </footer>
      </div>

      {preview && (
        <div
          className="fixed inset-0 z-50 flex flex-col bg-gray-950"
          onClick={(e) => { if (e.target === e.currentTarget) setPreview(null); }}
        >
          <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800 flex-shrink-0">
            <div className="flex items-center gap-3 min-w-0">
              <button
                onClick={() => setPreview(null)}
                className="text-gray-400 hover:text-white transition-colors text-sm flex items-center gap-1 flex-shrink-0"
                aria-label="トップへ戻る"
              >
                ← トップへ
              </button>
              <span className="w-1 h-5 rounded-full flex-shrink-0" style={{ background: preview.color }} />
              <span className="font-semibold truncate">{preview.name}</span>
              <span className="text-gray-500 text-xs flex-shrink-0">{scaleInfo.label}</span>
              <span className="text-gray-500 text-xs hidden sm:inline flex-shrink-0">ドラッグで回転 / スクロールでズーム</span>
            </div>
            <button
              onClick={() => setPreview(null)}
              className="text-gray-500 hover:text-white transition-colors text-xl leading-none px-2"
              aria-label="閉じる"
            >
              ✕
            </button>
          </div>
          <div className="flex-1 min-h-0">
            <StlViewer url={stlUrl(preview.path)} color={preview.color} />
          </div>
        </div>
      )}
    </>
  );
}
