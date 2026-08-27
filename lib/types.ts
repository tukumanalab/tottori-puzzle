export interface MunicipalityInfo {
  no: number;   // 1〜19 の通し番号（全国地方公共団体コード順）
  code: string; name: string; nameEn: string; color: string;
}

export interface BBox { minLon: number; maxLon: number; minLat: number; maxLat: number; }

export interface ScaleInfo {
  key: string; label: string; note: string;
}

export interface HeightInfo {
  key: string; label: string; note: string;
}

export interface PieceInfo {
  code: string; name: string;
  members: string[];   // 1 ピースにまとめた市町村コード
  w: number; h: number; z: number;
  relief: number;      // 海面より上の高さ（地形の起伏）
  base: number;        // 海面より下の厚み（溝を彫ると 3mm より厚くなる）
  tri: number; mb: number;
}

export interface FrameSection {
  file: string; key: string; label: string;
  w: number; h: number; tri: number; mb: number;
}

export interface FrameScale {
  label: string; note: string;
  overall: { w: number; h: number };
  sections: FrameSection[];
}

// 縮尺キー → 高さ倍率キー → 市町村コード
export type PieceManifest = Record<string, Record<string, Record<string, PieceInfo>>>;
export type FrameManifest = Record<string, FrameScale>;
