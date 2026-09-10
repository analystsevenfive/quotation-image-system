import type { NextConfig } from 'next';
let apiUrl = (process.env.API_URL || 'http://127.0.0.1:8000').trim();
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
