import type { MunicipalityInfo } from '../types';

// 東部（鳥取市・岩美郡・八頭郡）
export const TOBU: MunicipalityInfo[] = [
  { code:'31201', name:'鳥取市',   nameEn:'Tottori',     color:'#ef4444' },
  { code:'31302', name:'岩美町',   nameEn:'Iwami',       color:'#f97316' },
  { code:'31325', name:'若桜町',   nameEn:'Wakasa',      color:'#f59e0b' },
  { code:'31328', name:'智頭町',   nameEn:'Chizu',       color:'#eab308' },
  { code:'31329', name:'八頭町',   nameEn:'Yazu',        color:'#fb923c' },
];

// 中部（倉吉市・東伯郡）
export const CHUBU: MunicipalityInfo[] = [
  { code:'31203', name:'倉吉市',   nameEn:'Kurayoshi',   color:'#84cc16' },
  { code:'31364', name:'三朝町',   nameEn:'Misasa',      color:'#22c55e' },
  { code:'31370', name:'湯梨浜町', nameEn:'Yurihama',    color:'#10b981' },
  { code:'31371', name:'琴浦町',   nameEn:'Kotoura',     color:'#14b8a6' },
  { code:'31372', name:'北栄町',   nameEn:'Hokuei',      color:'#a3e635' },
];

// 西部（米子市・境港市・西伯郡・日野郡）
export const SEIBU: MunicipalityInfo[] = [
  { code:'31202', name:'米子市',   nameEn:'Yonago',      color:'#06b6d4' },
  { code:'31204', name:'境港市',   nameEn:'Sakaiminato', color:'#0ea5e9' },
  { code:'31384', name:'日吉津村', nameEn:'Hiezu',       color:'#38bdf8' },
  { code:'31386', name:'大山町',   nameEn:'Daisen',      color:'#3b82f6' },
  { code:'31389', name:'南部町',   nameEn:'Nanbu',       color:'#6366f1' },
  { code:'31390', name:'伯耆町',   nameEn:'Hoki',        color:'#818cf8' },
  { code:'31401', name:'日南町',   nameEn:'Nichinan',    color:'#a855f7' },
  { code:'31402', name:'日野町',   nameEn:'Hino',        color:'#c084fc' },
  { code:'31403', name:'江府町',   nameEn:'Kofu',        color:'#ec4899' },
];

export const BASE_PATH = process.env.NODE_ENV === 'production' ? '/tottori-puzzle' : '';
