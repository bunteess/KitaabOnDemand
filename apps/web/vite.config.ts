/// <reference types="vitest/config" />
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      "/api": process.env.VITE_DEV_API_PROXY ?? "http://localhost:8000",
    },
  },
  build: {
    sourcemap: false,
    chunkSizeWarningLimit: 600,
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    coverage: {
      provider: "v8",
      include: ["src/**/*.{ts,tsx}"],
      exclude: [
        "src/**/*.test.{ts,tsx}",
        "src/test/**",
        "src/api/schema.d.ts",
        "src/api/mock.ts",
        "src/main.tsx",
      ],
      thresholds: { lines: 75, statements: 75 },
    },
  },
});
