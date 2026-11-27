const path = require('node:path');

/** @type {import('next').NextConfig} */
const nextConfig = {
  images: { unoptimized: true },
  basePath: process.env.GITHUB_PAGES ? '/deriv-bot-next' : '',
  assetPrefix: process.env.GITHUB_PAGES ? '/deriv-bot-next/' : '',
  transpilePackages: ['@deriv/core'],
  turbopack: {
    alias: {
      '@deriv-com/smartcharts-champion': path.resolve(__dirname, 'lib/shims/smartcharts-champion.ts'),
      'technicalindicators': path.resolve(__dirname, 'lib/shims/technicalindicators.ts'),
    },
  },
  allowedDevOrigins: ['localhost', '10.42.0.1', '10.42.0.131'],
  typescript: {
    ignoreBuildErrors: true,
  },
}

module.exports = nextConfig
