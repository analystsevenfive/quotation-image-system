import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata = {
  title: 'Quotation Studio',
  description: 'Add product images to your quotations',
  icons: {
    icon: '/logo.png',
    shortcut: '/logo.png',
    apple: '/logo.png',
  },
};
export default function Layout({children}: {children: React.ReactNode}) { return <html lang="th"><body>{children}</body></html>; }
