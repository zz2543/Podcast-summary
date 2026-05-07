import { defineConfig } from "vitest/config";

export default defineConfig({
  server: {
    host: "127.0.0.1",
    proxy: {
      "/api/ws": {
        target: "ws://127.0.0.1:8000",
        ws: true,
        changeOrigin: true
      },
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true
      }
    }
  },
  test: {
    environment: "jsdom"
  }
});
