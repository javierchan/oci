/* Authenticate Playwright through the real local-session boundary before E2E. */

import { request, type FullConfig } from "@playwright/test";
import { chmod, rm } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";


const authStatePath = process.env.PLAYWRIGHT_AUTH_STATE_PATH
  ?? join(tmpdir(), "oci-dis-blueprint-playwright-auth.json");


export default async function globalSetup(config: FullConfig): Promise<() => Promise<void>> {
  const username = process.env.PLAYWRIGHT_AUTH_USERNAME?.trim();
  const password = process.env.PLAYWRIGHT_AUTH_PASSWORD;
  if (!username || !password) {
    throw new Error(
      "Browser E2E requires PLAYWRIGHT_AUTH_USERNAME and PLAYWRIGHT_AUTH_PASSWORD for a provisioned local user.",
    );
  }

  const apiBase = process.env.PLAYWRIGHT_API_URL ?? "http://localhost:8000";
  const context = await request.newContext({ baseURL: apiBase });
  try {
    const response = await context.post("/api/v1/auth/login", {
      data: { username, password },
    });
    if (!response.ok()) {
      const detail = (await response.text()).slice(0, 500);
      throw new Error(`Browser E2E authentication failed (${response.status()}): ${detail}`);
    }
    await context.storageState({ path: authStatePath });
    await chmod(authStatePath, 0o600);
  } finally {
    await context.dispose();
  }

  const configuredState = config.projects.every(
    (project) => project.use.storageState === authStatePath,
  );
  if (!configuredState) {
    await rm(authStatePath, { force: true });
    throw new Error("Every Playwright project must use the authenticated storage state.");
  }

  return async () => {
    await rm(authStatePath, { force: true });
  };
}
