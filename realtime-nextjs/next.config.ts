import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Emit a self-contained server bundle so the Docker image only needs the
  // standalone output + static assets, not the full node_modules tree.
  output: "standalone",
};

export default nextConfig;
