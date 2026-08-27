import * as fs from 'fs';
import * as path from 'path';
import * as https from 'https';
import * as http from 'http';
import JSZip from 'jszip';

// 鳥取県の市町村コード（4市 14町 1村 = 19 市町村）
const MUNICIPALITY_CODES = new Set([
  // 市
  '31201','31202','31203','31204',
  // 岩美郡
  '31302',
  // 八頭郡
  '31325','31328','31329',
  // 東伯郡
  '31364','31370','31371','31372',
  // 西伯郡
  '31384','31386','31389','31390',
  // 日野郡
  '31401','31402','31403',
]);

const OUT_DIR = path.join(process.cwd(), 'public', 'data', 'boundary');
const N03_URL = 'https://nlftp.mlit.go.jp/ksj/gml/data/N03/N03-2024/N03-20240101_31_GML.zip';

function download(url: string): Promise<Buffer> {
  return new Promise((resolve, reject) => {
    const proto = url.startsWith('https') ? https : http;
    proto.get(url, { timeout: 120000 }, (res) => {
      if (res.statusCode && res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        return resolve(download(res.headers.location));
      }
      if (res.statusCode !== 200) return reject(new Error(`HTTP ${res.statusCode} for ${url}`));
      const chunks: Buffer[] = [];
      res.on('data', (c: Buffer) => chunks.push(c));
      res.on('end', () => resolve(Buffer.concat(chunks)));
      res.on('error', reject);
    }).on('error', reject);
  });
}

interface GeoJsonFeature {
  type: 'Feature';
  properties: {
    N03_001: string | null;
    N03_002: string | null;
    N03_003: string | null;
    N03_004: string | null;
    N03_005: string | null;
    N03_007: string | null;
  };
  geometry: {
    type: 'Polygon' | 'MultiPolygon';
    coordinates: number[][][][] | number[][][];
  };
}

async function main() {
  fs.mkdirSync(OUT_DIR, { recursive: true });

  const missing = [...MUNICIPALITY_CODES].filter(c => !fs.existsSync(path.join(OUT_DIR, `${c}.json`)));
  if (missing.length === 0) {
    console.log('すべての境界ファイルが存在します。スキップ。');
    return;
  }
  console.log(`取得が必要なコード: ${missing.length} 件`);

  console.log('鳥取県（N03-2024 GeoJSON）をダウンロード中...');
  const buf = await download(N03_URL);
  const zip = await JSZip.loadAsync(buf);

  const geojsonFile = Object.keys(zip.files).find(f => f.endsWith('.geojson'));
  if (!geojsonFile) throw new Error('GeoJSON ファイルが ZIP 内に見つかりません');
  console.log(`  GeoJSON: ${geojsonFile}`);

  const geojsonStr = await zip.files[geojsonFile].async('string');
  const geojson = JSON.parse(geojsonStr) as { features: GeoJsonFeature[] };
  console.log(`  フィーチャ数: ${geojson.features.length}`);

  // N03_007 でポリゴンをグループ化
  const grouped = new Map<string, { rings: number[][][]; name: string }>();

  for (const feat of geojson.features) {
    const code = feat.properties.N03_007;
    if (!code || !MUNICIPALITY_CODES.has(code)) continue;

    const name = feat.properties.N03_004 ?? feat.properties.N03_005 ?? '';
    if (!grouped.has(code)) grouped.set(code, { rings: [], name });

    const geom = feat.geometry;
    if (geom.type === 'Polygon') {
      grouped.get(code)!.rings.push(geom.coordinates as number[][][]);
    } else if (geom.type === 'MultiPolygon') {
      for (const poly of geom.coordinates as number[][][][]) {
        grouped.get(code)!.rings.push(poly);
      }
    }
  }

  console.log(`  市町村コード数: ${grouped.size}`);

  for (const [code, { rings, name }] of grouped) {
    const outFile = path.join(OUT_DIR, `${code}.json`);
    if (fs.existsSync(outFile)) {
      console.log(`  ${code}.json 既存、スキップ`);
      continue;
    }
    const feature = {
      type: 'Feature',
      properties: { code, name },
      geometry: { type: 'MultiPolygon', coordinates: rings },
    };
    fs.writeFileSync(outFile, JSON.stringify(feature));
    console.log(`  ${code}.json 書き込み完了 (${name}, ${rings.length} ポリゴン)`);
  }

  for (const code of MUNICIPALITY_CODES) {
    if (!grouped.has(code) && !fs.existsSync(path.join(OUT_DIR, `${code}.json`))) {
      console.warn(`  警告: ${code} のデータが見つかりません`);
    }
  }

  console.log('完了。');
}

main().catch(e => { console.error(e); process.exit(1); });
