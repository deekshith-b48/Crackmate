import path from "node:path";
import type { NextConfig } from "next";

// Static export: FastAPI serves web/out in production, so there is no Node server at runtime.
const config: NextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
  // A lockfile in a parent folder can make Next pick the wrong project root.
  turbopack: { root: path.resolve(process.cwd()) },
};

export default config;
