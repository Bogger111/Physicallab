import type { NextConfig } from "next";
import path from "node:path";

const nextConfig: NextConfig = {
  // GitHub Pages serves the static export from frontend/out.
  output: "export",
  trailingSlash: true,
  basePath: process.env.NEXT_PUBLIC_BASE_PATH || "",
  assetPrefix: process.env.NEXT_PUBLIC_BASE_PATH || undefined,
  // Monorepo root: the client imports the authoritative experiment config
  // from ../backend so record sheets, reports and UI share one schema.
  turbopack: {
    root: path.join(__dirname, ".."),
  },
};

export default nextConfig;
