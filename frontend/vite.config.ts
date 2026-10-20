import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  envDir: "..", // reads VITE_API_BASE_URL from the root .env
  test: { environment: "node" },
});