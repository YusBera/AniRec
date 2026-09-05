/// <reference types="node" />
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// The API runs on loopback and the dev server proxies to it, so the browser
// only ever talks to one origin. That keeps the development setup identical in
// shape to the packaged one, where a desktop shell would serve the built files
// and the API from the same place, and it means CORS is a fallback rather than
// the mechanism the app depends on.
const API_ORIGIN = process.env.ANIREC_API ?? "http://127.0.0.1:8770";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: API_ORIGIN,
        changeOrigin: true,
        // Server-sent events must not be buffered by the proxy or progress
        // arrives all at once when the operation finishes, which defeats it.
        configure: (proxy) => {
          proxy.on("proxyRes", (proxyRes) => {
            if (proxyRes.headers["content-type"]?.includes("text/event-stream")) {
              proxyRes.headers["cache-control"] = "no-cache";
            }
          });
        },
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: true,
  },
});
