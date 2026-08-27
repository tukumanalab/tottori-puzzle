export interface MunicipalityInfo {
  code: string; name: string; nameEn: string; color: string;
}

export interface BBox { minLon: number; maxLon: number; minLat: number; maxLat: number; }

export interface ScaleInfo {
  key: string; label: string; note: string;
}

export interface PieceInfo {
  code: string; name: string;
  w: number; h: number; z: number; tri: number; mb: number;
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

export type PieceManifest = Record<string, Record<string, PieceInfo>>;
export type FrameManifest = Record<string, FrameScale>;
