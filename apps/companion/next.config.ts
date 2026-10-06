import type { NextConfig } from 'next';
const config: NextConfig = {
  turbopack: { root: process.cwd() },
  async rewrites() { return [{ source: '/api/:path*', destination: `${process.env.API_INTERNAL_URL || 'http://127.0.0.1:8000'}/:path*` }]; },
  async headers() { return [{source: '/:path*', headers: [{key: 'X-Frame-Options', value: 'DENY'}, {key: 'X-Content-Type-Options', value: 'nosniff'}, {key: 'Referrer-Policy', value: 'same-origin'}]}]; }
};
export default config;
