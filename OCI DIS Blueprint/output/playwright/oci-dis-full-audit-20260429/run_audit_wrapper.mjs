/* Replays the 20260428 full-app audit harness into a new dated output directory. */

import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";

const ROOT = process.cwd();
const SOURCE_SCRIPT = path.join(ROOT, "output/playwright/oci-dis-full-audit-20260428/capture_audit.mjs");
const TARGET_DIR = path.join(ROOT, "output/playwright/oci-dis-full-audit-20260429");
const TARGET_SCRIPT = path.join(TARGET_DIR, "capture_audit.mjs");

async function main() {
  await mkdir(TARGET_DIR, { recursive: true });
  const source = await readFile(SOURCE_SCRIPT, "utf8");
  const nextSource = source.replace(
    'const OUT_DIR = path.join(ROOT, "output/playwright/oci-dis-full-audit-20260428");',
    'const OUT_DIR = path.join(ROOT, "output/playwright/oci-dis-full-audit-20260429");',
  ).replace(
    `      if (themeValue === "dark") {\n        document.documentElement.classList.add("dark");\n      }\n      if (themeValue === "light") {\n        document.documentElement.classList.remove("dark");\n      }`,
    `      const root = document.documentElement;\n      if (!root) {\n        return;\n      }\n      if (themeValue === "dark") {\n        root.classList.add("dark");\n      }\n      if (themeValue === "light") {\n        root.classList.remove("dark");\n      }`,
  );

  await writeFile(TARGET_SCRIPT, nextSource, "utf8");
  await import(pathToFileURL(TARGET_SCRIPT).href);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
