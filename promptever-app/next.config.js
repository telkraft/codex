/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  
  // Environment variables
  env: {
    NEXT_PUBLIC_APP_NAME: 'Promptever',
    NEXT_PUBLIC_APP_VERSION: '1.0.0',
  },
  
  // Rewrites for API proxy (development)
  async rewrites() {
    return [
      {
        source: '/api/rag/:path*',
        destination: `${process.env.RAG_API_INTERNAL_URL || 'http://localhost:9009'}/:path*`,
      },
    ];
  },
  
  // Headers for security
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          { key: 'X-Frame-Options', value: 'SAMEORIGIN' },
          { key: 'X-Content-Type-Options', value: 'nosniff' },
        ],
      },
    ];
  },
};

module.exports = nextConfig;
