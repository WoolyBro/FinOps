/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,

  // A production build writes to the same directory the dev server serves
  // from, which silently corrupts a running `next dev` -- it starts throwing
  // "Cannot find module './98.js'" because its chunks were replaced underneath
  // it. Letting the output directory be overridden means a verification build
  // can go somewhere else entirely.
  distDir: process.env.NEXT_DIST_DIR || ".next",
};

export default nextConfig;
