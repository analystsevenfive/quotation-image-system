import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata = {
  title: 'Quotation Studio · Seven Five',
  description: 'Add product images to your quotations',
  icons: {
    icon: '/logo.png',
    shortcut: '/logo.png',
    apple: '/logo.png',
  },
};

export default function Layout({children}: {children: React.ReactNode}) {
  return (
    <html lang="th">
      <head>
        <meta name="theme-color" content="#0b3b31" />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Noto+Sans+Thai:wght@400;500;600;700;800&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
