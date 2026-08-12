import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const rendererPort = Number(process.env.VITE_RENDERER_PORT || 17888);

export default defineConfig({
  root: "electron/renderer",
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    clearMocks: true,
  },
  build: {
    outDir: "../../dist/renderer",
    emptyOutDir: true,
  },
  server: {
    host: "127.0.0.1",
    port: rendererPort,
    strictPort: true,
  },
});
