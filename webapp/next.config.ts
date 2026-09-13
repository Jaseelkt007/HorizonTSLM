import type { NextConfig } from "next";

// Static export: `next build` writes a self-contained site to out/ (no server, no API calls).
const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  reactStrictMode: true,
};

export default nextConfig;
