const path = require('node:path');

/** @type {import('next').NextConfig} */
const nextConfig = {
  images: { unoptimized: true },
  basePath: process.env.GITHUB_PAGES ? '/deriv-bot-next' : '',
  assetPrefix: process.env.GITHUB_PAGES ? '/deriv-bot-next/' : '',
  transpilePackages: ['@deriv/core'],
  turbopack: {
    root: path.resolve(__dirname),
  },
  allowedDevOrigins: ['localhost', '10.42.0.1', '10.42.0.131'],
  typescript: {
    ignoreBuildErrors: true,
  },
  webpack: (config) => {
    config.resolve.alias = {
      ...config.resolve.alias,
      '@deriv-com/smartcharts-champion': path.resolve(__dirname, 'lib/shims/smartcharts-champion.ts'),
      'technicalindicators': path.resolve(__dirname, 'lib/shims/technicalindicators.ts'),
    };
    return config;
  },
}

module.exports = nextConfig
