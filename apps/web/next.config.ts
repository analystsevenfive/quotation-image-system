import type { NextConfig } from 'next';
let rawApiUrl = (process.env.API_URL || process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000').trim();
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
