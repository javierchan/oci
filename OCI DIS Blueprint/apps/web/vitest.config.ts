/* Vitest configuration for focused web unit-test discovery. */

import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: [
      "**/*.test.ts",
      "**/*.test.tsx",
      "**/*.spec.ts",
      "**/*.spec.tsx",
    ],
    exclude: ["e2e/**", "node_modules/**"],
  },
});
