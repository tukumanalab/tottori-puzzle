import type { MunicipalityInfo, ScaleInfo, HeightInfo } from '../types';

// 東部（鳥取市・岩美郡・八頭郡）
export const TOBU: MunicipalityInfo[] = [
  { no: 1, code:'31201', name:'鳥取市',   nameEn:'Tottori',     color:'#ef4444' },
  { no: 5, code:'31302', name:'岩美町',   nameEn:'Iwami',       color:'#f97316' },
  { no: 6, code:'31325', name:'若桜町',   nameEn:'Wakasa',      color:'#f59e0b' },
  { no: 7, code:'31328', name:'智頭町',   nameEn:'Chizu',       color:'#eab308' },
  { no: 8, code:'31329', name:'八頭町',   nameEn:'Yazu',        color:'#fb923c' },
];

// 中部（倉吉市・東伯郡）
export const CHUBU: MunicipalityInfo[] = [
  { no: 3, code:'31203', name:'倉吉市',   nameEn:'Kurayoshi',   color:'#84cc16' },
  { no: 9, code:'31364', name:'三朝町',   nameEn:'Misasa',      color:'#22c55e' },
  { no:10, code:'31370', name:'湯梨浜町', nameEn:'Yurihama',    color:'#10b981' },
  { no:11, code:'31371', name:'琴浦町',   nameEn:'Kotoura',     color:'#14b8a6' },
  { no:12, code:'31372', name:'北栄町',   nameEn:'Hokuei',      color:'#a3e635' },
];

// 西部（米子市・境港市・西伯郡・日野郡）
export const SEIBU: MunicipalityInfo[] = [
  { no: 2, code:'31202', name:'米子市・日吉津村', nameEn:'Yonago-Hiezu', color:'#06b6d4' },
  { no: 4, code:'31204', name:'境港市',   nameEn:'Sakaiminato', color:'#0ea5e9' },
  { no:13, code:'31386', name:'大山町',   nameEn:'Daisen',      color:'#3b82f6' },
  { no:14, code:'31389', name:'南部町',   nameEn:'Nanbu',       color:'#6366f1' },
  { no:15, code:'31390', name:'伯耆町',   nameEn:'Hoki',        color:'#818cf8' },
  { no:16, code:'31401', name:'日南町',   nameEn:'Nichinan',    color:'#a855f7' },
  { no:17, code:'31402', name:'日野町',   nameEn:'Hino',        color:'#c084fc' },
  { no:18, code:'31403', name:'江府町',   nameEn:'Kofu',        color:'#ec4899' },
];

// 縮尺（scripts/scales.py と対応）
export const SCALES: ScaleInfo[] = [
  { key: '300k', label: '1/300,000', note: '等倍' },
  { key: '600k', label: '1/600,000', note: '1/2' },
  { key: '900k', label: '1/900,000', note: '1/3' },
];

export const DEFAULT_SCALE = '300k';

// 高さ（Z 方向）の倍率＝実寸に対する倍率（scripts/scales.py の HEIGHTS と対応）。
// 地形の起伏だけに掛かり、ベース厚さ 3mm には掛からない。
// 枠は境界データだけから作るため高さの影響を受けず、両モードで共通。
export const HEIGHTS: HeightInfo[] = [
  { key: 'z10', label: '実寸',        note: '通常' },
  { key: 'z30', label: '実寸の 3 倍', note: '強調' },
];

export const DEFAULT_HEIGHT = 'z10';

export const BASE_PATH = process.env.NODE_ENV === 'production' ? '/tottori-puzzle' : '';
