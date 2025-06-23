/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  trailingSlash: false,
  
  // Docker deployment: Direct API access via host-mapped ports
  // No rewrites needed - frontend uses NEXT_PUBLIC_API_BASE_URL
  
  async rewrites() {
    return [];
  },
  
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          {
            key: 'X-Content-Type-Options',
            value: 'nosniff',
          },
        ],
      },
    ];
  },
};

export default nextConfig;
