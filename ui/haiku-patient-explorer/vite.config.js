import { defineConfig } from "vite";

const repoBase = "/PEAT-Nucleate-BIoHack-2026/";

export default defineConfig({
  root: ".",
  base: process.env.GITHUB_PAGES === "true" ? repoBase : "/",
  server: { port: 5173, host: true, strictPort: true, allowedHosts: true },
  preview: { port: 5173, host: true },
});
