const path = require('node:path');

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
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
  eslint: {
    ignoreDuringBuilds: true,
  },
}

module.exports = nextConfig
