/* Playwright configuration for critical production browser flows. */

import { defineConfig } from "@playwright/test";
import { join } from "node:path";
import { tmpdir } from "node:os";


const authStatePath = process.env.PLAYWRIGHT_AUTH_STATE_PATH
  ?? join(tmpdir(), "oci-dis-blueprint-playwright-auth.json");

export default defineConfig({
  testDir: "./e2e",
  globalSetup: "./e2e/global-setup.ts",
  outputDir: process.env.PLAYWRIGHT_OUTPUT_DIR ?? "test-results",
  timeout: 90_000,
  expect: {
    timeout: 15_000,
  },
  reporter: [
    ["list"],
    ["html", {
      outputFolder: process.env.PLAYWRIGHT_REPORT_DIR ?? "playwright-report",
      open: "never",
    }],
  ],
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3000",
    channel: process.env.PLAYWRIGHT_BROWSER_CHANNEL,
    storageState: authStatePath,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
  },
});
