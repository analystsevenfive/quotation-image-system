import type { NextConfig } from 'next';
const fallbackUrl = (process.env.VERCEL || process.env.NODE_ENV === 'production')
  ? 'https://quotation-api-h4ta.onrender.com'
  : 'http://127.0.0.1:8000';

let rawApiUrl = (process.env.API_URL || process.env.NEXT_PUBLIC_API_URL || fallbackUrl).trim();
rawApiUrl = rawApiUrl.replace(/^["']|["']$/g, '').trim();
let apiUrl = rawApiUrl;
if (!apiUrl.startsWith('http://') && !apiUrl.startsWith('https://')) {
  apiUrl = `https://${apiUrl}`;
}
apiUrl = apiUrl.replace(/\/+$/, '');

const config: NextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${apiUrl}/api/:path*`,
      },
    ];
  },
};
export default config;
