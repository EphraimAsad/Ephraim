import { defineConfig, externalizeDepsPlugin } from "electron-vite";
import react from "@vitejs/plugin-react";
export default defineConfig({
  main: {
    plugins: [externalizeDepsPlugin()],
    build: { rollupOptions: { external: ["node-llama-cpp", "pdf-parse", "mammoth", "exceljs", "node:sqlite"] } }
  },
  preload: { plugins: [externalizeDepsPlugin()] },
  renderer: { plugins: [react()] }
});
