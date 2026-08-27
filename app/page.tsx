'use client';
import { useState } from 'react';
import dynamic from 'next/dynamic';
import { SEIBU, CHUBU, TOBU, BASE_PATH } from '../lib/constants/tottori';
import type { MunicipalityInfo } from '../lib/types';

const StlViewer = dynamic(() => import('./components/StlViewer'), { ssr: false });

const GROUPS = [
  { label: '西部（米子市・境港市・西伯郡・日野郡）', zipName: 'tottori-puzzle-seibu.zip', municipalities: SEIBU },
  { label: '中部（倉吉市・東伯郡）',                 zipName: 'tottori-puzzle-chubu.zip', municipalities: CHUBU },
  { label: '東部（鳥取市・岩美郡・八頭郡）',         zipName: 'tottori-puzzle-tobu.zip',  municipalities: TOBU },
];

const FRAMES = [
  { label: '西部', file: 'frame_seibu.stl', size: '152 × 213 mm' },
  { label: '中部', file: 'frame_chubu.stl', size: '136 × 213 mm' },
  { label: '東部', file: 'frame_tobu.stl',  size: '146 × 213 mm' },
];

const README_TXT =
  '地形データ: 国土地理院 基盤地図情報数値標高モデル（DEM）\n' +
  '行政界データ: 国土交通省 国土数値情報（行政区域データ）N03-2024\n' +
  '本データは上記データを加工して作成したものです。\n';

export default function HomePage() {
  const [zippingKey, setZippingKey] = useState<string | null>(null);
  const [preview, setPreview] = useState<{ code: string; name: string; color: string } | null>(null);
  const [openGroups, setOpenGroups] = useState<Set<string>>(new Set(GROUPS.map(g => g.label)));
  const [excluded, setExcluded] = useState<Set<string>>(new Set());

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

  async function buildAndDownloadZip(municipalities: MunicipalityInfo[], zipName: string, key: string) {
    setZippingKey(key);
    try {
      const JSZip = (await import('jszip')).default;
      const zip = new JSZip();
      const targets = municipalities.filter(m => !excluded.has(m.code));
      await Promise.all(targets.map(async (m) => {
        const resp = await fetch(`${BASE_PATH}/data/stl/${m.code}.stl`);
        if (resp.ok) zip.file(`${m.code}_${m.nameEn}.stl`, await resp.arrayBuffer());
      }));
      zip.file('README.txt', README_TXT);
      const blob = await zip.generateAsync({ type: 'blob' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = zipName; a.click();
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
                  {group.municipalities.map((m) => (
                    <li key={m.code} className="flex items-center justify-between py-4 gap-4">
                      <div className="flex items-center gap-3 min-w-0">
                        <input
                          type="checkbox"
                          checked={!excluded.has(m.code)}
                          onChange={() => toggleExclude(m.code)}
                          className="w-4 h-4 flex-shrink-0 accent-emerald-500 cursor-pointer"
                        />
                        <span className="w-1 h-8 rounded-full flex-shrink-0" style={{ background: m.color }} />
                        <div className={excluded.has(m.code) ? 'opacity-40' : ''}>
                          <span className="font-semibold">{m.name}</span>
                          <span className="ml-2 text-gray-500 text-sm">{m.nameEn}</span>
                        </div>
                      </div>
                      <div className="flex items-center gap-4 flex-shrink-0">
                        <button
                          onClick={() => setPreview({ code: m.code, name: m.name, color: m.color })}
                          className="text-sm text-gray-500 hover:text-gray-200 transition-colors"
                        >
                          プレビュー
                        </button>
                        <a
                          href={`${BASE_PATH}/data/stl/${m.code}.stl`}
                          download={`${m.code}_${m.nameEn}.stl`}
                          className="bg-blue-600 hover:bg-blue-500 transition-colors px-3 py-1.5 rounded text-sm font-medium"
                        >
                          ダウンロード
                        </a>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          );
        })}

        <button
          onClick={() => buildAndDownloadZip(GROUPS.flatMap(g => g.municipalities), 'tottori-puzzle-all.zip', 'all')}
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
            ピースをはめ込むトレイ型の枠です。3 つのセクションをつなげて一体の枠（全体 ~421 × 213 mm）として使用できます。
          </p>
          <div className="flex flex-col gap-2">
            {FRAMES.map(({ label, file, size }) => (
              <div key={file} className="flex items-center justify-between py-2 border-b border-gray-800 last:border-0">
                <div>
                  <span className="font-medium text-sm">{label}</span>
                  <span className="ml-2 text-gray-500 text-xs">{size}</span>
                </div>
                <div className="flex items-center gap-4 flex-shrink-0">
                  <button
                    onClick={() => setPreview({ code: file.replace('.stl', ''), name: `枠 — ${label}`, color: '#888888' })}
                    className="text-sm text-gray-500 hover:text-gray-200 transition-colors"
                  >
                    プレビュー
                  </button>
                  <a
                    href={`${BASE_PATH}/data/stl/${file}`}
                    download={file}
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
            <div className="flex items-center gap-3">
              <button
                onClick={() => setPreview(null)}
                className="text-gray-400 hover:text-white transition-colors text-sm flex items-center gap-1"
                aria-label="トップへ戻る"
              >
                ← トップへ
              </button>
              <span className="w-1 h-5 rounded-full flex-shrink-0" style={{ background: preview.color }} />
              <span className="font-semibold">{preview.name}</span>
              <span className="text-gray-500 text-xs hidden sm:inline">ドラッグで回転 / スクロールでズーム</span>
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
            <StlViewer
              url={`${BASE_PATH}/data/stl/${preview.code}.stl`}
              color={preview.color}
            />
          </div>
        </div>
      )}
    </>
  );
}
