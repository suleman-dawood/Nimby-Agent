import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30000,
  use: {
    baseURL: "http://localhost:3000",
    headless: true,
  },
  webServer: {
    command: "NEXT_PUBLIC_API_URL=https://api-service-production-6a0d.up.railway.app npm run dev",
    port: 3000,
    timeout: 60000,
    reuseExistingServer: true,
  },
});
