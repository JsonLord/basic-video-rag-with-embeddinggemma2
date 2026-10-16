/** @type {import('next').NextConfig} */
const nextConfig = {
    output: 'standalone',
    eslint: {
        ignoreDuringBuilds: true,
    },
    async rewrites() {
        return [
            {
                source: '/api/:path*',
                destination: 'http://127.0.0.1:8000/api/:path*',
            },
            {
                source: '/api-docs',
                destination: 'http://127.0.0.1:8000/api-docs',
            },
            {
                source: '/health',
                destination: 'http://127.0.0.1:8000/health',
            },
            {
                source: '/docs',
                destination: 'http://127.0.0.1:8000/docs',
            },
            {
                source: '/openapi.json',
                destination: 'http://127.0.0.1:8000/openapi.json',
            },
            {
                source: '/media/:path*',
                destination: 'http://127.0.0.1:8000/media/:path*',
            },
        ];
    },
};
export default nextConfig;
