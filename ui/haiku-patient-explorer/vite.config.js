import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";

const rootDir = path.dirname(fileURLToPath(import.meta.url));
const demoDir = path.resolve(rootDir, "../../../demo");
const base = process.env.EXPLORER_BASE || "/";

export default defineConfig({
  root: ".",
  base,
  server: {
    port: 5173,
    host: true,
    strictPort: true,
    allowedHosts: true,
    fs: { allow: [rootDir, demoDir] },
    proxy: {
      "/demo": {
        target: "http://127.0.0.1:8080",
        changeOrigin: true,
      },
      "/api": {
        target: "http://127.0.0.1:8080",
        changeOrigin: true,
      },
    },
  },
  preview: { port: 5173, host: true },
});
