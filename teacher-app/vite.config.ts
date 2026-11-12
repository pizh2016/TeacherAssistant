import { defineConfig, loadEnv } from "vite";
import vue from "@vitejs/plugin-vue";
import { resolve } from "path";

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  // Load environment variables from .env files
  const env = loadEnv(mode, process.cwd(), "");
  const apiPort = env.VITE_API_PORT || "18800";
  const apiHost = env.VITE_API_HOST || "localhost";
  const apiUrl = `http://${apiHost}:${apiPort}`;

  return {
    plugins: [vue()],

    // Relative base path for deployment under /static/teacher/
    base: "./",

    resolve: {
      alias: {
        "@": resolve(__dirname, "src"),
      },
    },

    // Dev server configuration
    server: {
      port: 5173,
      host: "0.0.0.0",
      // Proxy API requests to the backend during development
      proxy: {
        "/api": {
          target: apiUrl,
          changeOrigin: true,
        },
        "/ws": {
          target: apiUrl.replace("http://", "ws://"),
          ws: true,
        },
      },
    },

    // Build output configuration
    build: {
      outDir: "dist",
      assetsDir: "assets",
      rollupOptions: {
        output: {
          manualChunks: {
            vendor: ["vue", "vue-router"],
          },
        },
      },
    },
  };
});
