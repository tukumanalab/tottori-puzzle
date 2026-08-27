import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: '鳥取県 3D 市町村パズル',
  description: '鳥取県の市町村の地形3Dパズルデータを生成・ダウンロード',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ja">
      <body className="bg-gray-950 text-gray-100 min-h-screen">{children}</body>
    </html>
  );
}
