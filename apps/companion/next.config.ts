import type { NextConfig } from 'next';
const config: NextConfig = {
  turbopack: { root: process.cwd() },
  async rewrites() { const backend = process.env.API_INTERNAL_URL || 'http://127.0.0.1:8000'; return [{ source: '/api/bijaksense/:path*', destination: `${backend}/api/bijaksense/:path*` }, { source: '/api/:path*', destination: `${backend}/:path*` }]; },
  async headers() { return [{source: '/:path*', headers: [{key: 'X-Frame-Options', value: 'DENY'}, {key: 'X-Content-Type-Options', value: 'nosniff'}, {key: 'Referrer-Policy', value: 'same-origin'}]}]; }
};
export default config;
