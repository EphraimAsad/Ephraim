import { defineConfig, externalizeDepsPlugin } from "electron-vite";
import react from "@vitejs/plugin-react";
export default defineConfig({
  main: {
    plugins: [externalizeDepsPlugin()],
    build: { rollupOptions: { external: ["node-llama-cpp", "pdf-parse", "mammoth", "exceljs", "node:sqlite"] } }
  },
  preload: {
    plugins: [externalizeDepsPlugin()],
    // A sandboxed renderer cannot execute an ESM (.mjs) preload.
    // Force one self-contained CommonJS bridge, preserving sandbox:true.
    build: { rollupOptions: { output: { format: "cjs", entryFileNames: "index.cjs" } } }
  },
  renderer: {
    // The packaged renderer opens via file://. Root-relative asset URLs load
    // from the filesystem root and leave the Electron window blank.
    base: "./",
    plugins: [react()]
  }
});
