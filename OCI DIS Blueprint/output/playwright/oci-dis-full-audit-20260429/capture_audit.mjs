/* Exhaustive visual and functional capture workflow for OCI DIS Blueprint. */

import fs from "node:fs/promises";
import path from "node:path";

import { chromium } from "playwright";

const ROOT = process.cwd();
const BASE_URL = "http://localhost:3000";
const API_URL = "http://localhost:8000/api/v1";
const THEME_STORAGE_KEY = "oci-dis-theme";
const OUT_DIR = path.join(ROOT, "output/playwright/oci-dis-full-audit-20260429");
const SCREENSHOT_DIR = path.join(OUT_DIR, "screens");
const MANIFEST_PATH = path.join(OUT_DIR, "manifest.json");

const COMPONENT_INVENTORY = [
  "admin-assumption-form",
  "admin-confirm-delete",
  "admin-dictionary-form",
  "admin-pattern-form",
  "breadcrumb",
  "capture-history-client",
  "capture-step-destination",
  "capture-step-identity",
  "capture-step-review",
  "capture-step-source",
  "capture-step-technical",
  "capture-wizard",
  "catalog-table",
  "complexity-badge",
  "graph-controls",
  "graph-detail-panel",
  "graph-export-button",
  "import-upload",
  "integration-canvas",
  "integration-design-canvas-panel",
  "integration-graph",
  "integration-patch-form",
  "modal",
  "nav",
  "oic-estimate-preview",
  "pattern-badge",
  "pattern-support-badge",
  "projects-page-client",
  "qa-badge",
  "qa-preview",
  "raw-column-values-table",
  "recalculate-button",
  "skeleton",
  "system-autocomplete",
  "theme-toggle",
  "toast",
  "truncated-cell",
  "volumetry-card",
];

const manifest = {
  generated_at: new Date().toISOString(),
  out_dir: OUT_DIR,
  screenshots_dir: SCREENSHOT_DIR,
  base_url: BASE_URL,
  api_url: API_URL,
  project: null,
  dynamic_ids: {},
  captures: [],
  coverage: {
    inventory: COMPONENT_INVENTORY,
    covered: [],
    missing: [],
  },
  console_errors: {},
  failures: [],
};

async function ensureDirs() {
  await fs.mkdir(SCREENSHOT_DIR, { recursive: true });
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status} for ${url}`);
  }
  return response.json();
}

function screenshotPath(name) {
  return path.join(SCREENSHOT_DIR, `${name}.png`);
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function withContext(browser, options, fn) {
  const viewport = options.viewport ?? { width: 1440, height: 980 };
  const theme = options.theme ?? "light";
  const context = await browser.newContext({
    viewport,
    colorScheme: theme === "dark" ? "dark" : "light",
  });
  await context.addInitScript(
    ({ storageKey, themeValue }) => {
      window.localStorage.setItem(storageKey, themeValue);
      const root = document.documentElement;
      if (!root) {
        return;
      }
      if (themeValue === "dark") {
        root.classList.add("dark");
      }
      if (themeValue === "light") {
        root.classList.remove("dark");
      }
    },
    { storageKey: THEME_STORAGE_KEY, themeValue: theme },
  );
  try {
    return await fn(context);
  } finally {
    await context.close();
  }
}

function attachErrorCollectors(page, captureName) {
  const errors = [];
  page.on("console", (message) => {
    if (message.type() === "error") {
      errors.push(`[console] ${message.text()}`);
    }
  });
  page.on("pageerror", (error) => {
    errors.push(`[pageerror] ${String(error)}`);
  });
  manifest.console_errors[captureName] = errors;
  return errors;
}

async function gotoPage(page, url, waitUntil = "networkidle") {
  await page.goto(url, { waitUntil, timeout: 30000 });
  await page.waitForLoadState("domcontentloaded");
}

function locatorText(locator) {
  return locator.evaluate((element) => element.textContent ?? "").catch(() => "");
}

async function recordCapture(page, details) {
  const filePath = screenshotPath(details.name);
  await page.screenshot({
    path: filePath,
    fullPage: details.fullPage ?? true,
  });

  manifest.captures.push({
    name: details.name,
    path: filePath,
    url: page.url(),
    viewport: details.viewport ?? page.viewportSize(),
    theme: details.theme ?? "light",
    components: details.components ?? [],
    notes: details.notes ?? "",
    console_errors: manifest.console_errors[details.name] ?? [],
  });
  console.log(`Captured ${details.name} -> ${filePath}`);
}

async function captureRoute(browser, options) {
  const viewport = options.viewport ?? { width: 1440, height: 980 };
  try {
    return await withContext(
      browser,
      { viewport, theme: options.theme ?? "light" },
      async (context) => {
        const page = await context.newPage();
        attachErrorCollectors(page, options.name);

        if (options.beforeGoto) {
          await options.beforeGoto(page, context);
        }
        await gotoPage(page, options.url, options.waitUntil ?? "networkidle");
        if (options.afterGoto) {
          await options.afterGoto(page, context);
        }
        await recordCapture(page, {
          name: options.name,
          theme: options.theme ?? "light",
          viewport,
          components: options.components,
          notes: options.notes,
          fullPage: options.fullPage,
        });
      },
    );
  } catch (error) {
    manifest.failures.push({
      capture: options.name,
      url: options.url,
      error: String(error),
    });
    console.error(`Capture failed: ${options.name}`);
    console.error(error);
    return null;
  }
}

async function clickIfPresent(page, selector, options = {}) {
  const locator = page.locator(selector).first();
  if (await locator.count()) {
    await locator.click(options);
    return true;
  }
  return false;
}

async function fillIfPresent(page, selector, value) {
  const locator = page.locator(selector).first();
  if (await locator.count()) {
    await locator.fill(value);
    return true;
  }
  return false;
}

async function fillByLabel(page, label, value) {
  const locator = page.getByLabel(label, { exact: true }).first();
  if (await locator.count()) {
    await locator.fill(value);
    return true;
  }
  return false;
}

async function selectFirstMatchingOption(page, label, matcher) {
  const locator = page.getByLabel(label, { exact: true }).first();
  if (!(await locator.count())) {
    return false;
  }
  const options = (await locator.locator("option").allTextContents())
    .map((text) => text.trim())
    .filter((text) => text !== "");
  const target =
    options.find((text) => !/^select /i.test(text) && matcher(text)) ??
    options.find((text) => !/^select /i.test(text));
  if (!target) {
    return false;
  }
  await locator.selectOption({ label: target }).catch(() => {});
  return true;
}

async function waitForStep(page, title) {
  await page.getByRole("heading", { name: title, exact: true }).waitFor({
    state: "visible",
    timeout: 5000,
  });
}

async function captureProjects(browser, project) {
  const projectUrl = `${BASE_URL}/projects`;

  await captureRoute(browser, {
    name: "01_projects_baseline",
    url: projectUrl,
    components: ["nav", "theme-toggle", "projects-page-client"],
    notes: "Projects landing page baseline with project cards/table and persistent navigation.",
  });

  await captureRoute(browser, {
    name: "02_projects_search_active",
    url: projectUrl,
    components: ["projects-page-client"],
    notes: "Projects page with search filter active.",
    afterGoto: async (page) => {
      await fillIfPresent(page, 'input[placeholder="Filter by project name..."]', "NovaBrand");
      await delay(300);
    },
  });

  await captureRoute(browser, {
    name: "03_projects_new_form",
    url: projectUrl,
    components: ["projects-page-client"],
    notes: "Projects page with create form expanded.",
    afterGoto: async (page) => {
      await page.getByRole("button", { name: "New Project" }).click();
      await delay(200);
    },
  });

  await captureRoute(browser, {
    name: "04_projects_archive_modal",
    url: projectUrl,
    components: ["projects-page-client", "modal"],
    notes: "ConfirmModal opened from an Archive action on the projects surface.",
    afterGoto: async (page) => {
      await page.getByRole("button", { name: "Archive" }).first().click();
      await delay(250);
    },
  });

  await captureRoute(browser, {
    name: "05_projects_toast_validation",
    url: projectUrl,
    components: ["projects-page-client", "toast"],
    notes: "ToastStack validation error triggered without mutating data.",
    afterGoto: async (page) => {
      await page.getByRole("button", { name: "New Project" }).click();
      await delay(150);
      await page.getByRole("button", { name: "Create Project" }).click();
      await delay(300);
    },
  });

  await captureRoute(browser, {
    name: "06_projects_mobile",
    url: projectUrl,
    viewport: { width: 390, height: 844 },
    components: ["nav", "projects-page-client"],
    notes: "Projects page mobile layout.",
  });

  await captureRoute(browser, {
    name: "07_projects_dark",
    url: projectUrl,
    theme: "dark",
    components: ["nav", "theme-toggle", "projects-page-client"],
    notes: "Projects page dark theme.",
  });
}

async function captureDashboard(browser, projectId) {
  const url = `${BASE_URL}/projects/${projectId}`;
  await captureRoute(browser, {
    name: "08_dashboard_baseline",
    url,
    components: ["nav", "breadcrumb", "recalculate-button", "volumetry-card"],
    notes: "Project dashboard baseline with KPI strip and action header.",
  });

  await captureRoute(browser, {
    name: "09_dashboard_dark",
    url,
    theme: "dark",
    components: ["nav", "breadcrumb", "recalculate-button", "volumetry-card"],
    notes: "Project dashboard in dark theme.",
  });
}

async function captureImport(browser, projectId, importBatchId) {
  await captureRoute(browser, {
    name: "10_import_baseline",
    url: `${BASE_URL}/projects/${projectId}/import`,
    components: ["nav", "breadcrumb", "import-upload"],
    notes: "Import surface baseline with template/download/upload/history affordances.",
  });

  if (importBatchId) {
    await captureRoute(browser, {
      name: "11_import_batch_detail",
      url: `${BASE_URL}/projects/${projectId}/import?batch_id=${importBatchId}&row=1`,
      components: ["import-upload"],
      notes: "Import page with source-row table loaded for a completed batch.",
    });
  }
}

async function populateWizard(page, knownDuplicate) {
  await fillByLabel(page, "Brand", knownDuplicate.brand ?? "NovaBrand");
  await fillByLabel(page, "Business Process", knownDuplicate.business_process ?? "Order to Cash");
  await fillByLabel(page, "Interface Name", "Audit wizard coverage integration");
  await fillByLabel(page, "Interface ID", "AUDIT-WIZ-001");
  await fillByLabel(page, "Owner", "Architecture Team");
  await fillByLabel(page, "Description", "Guided capture walkthrough for audit evidence.");
  await fillByLabel(page, "Initial Scope", "Visual audit only");
}

async function captureCaptureWizard(browser, projectId, knownDuplicate) {
  const url = `${BASE_URL}/projects/${projectId}/capture/new`;

  await withContext(browser, { viewport: { width: 1440, height: 980 }, theme: "light" }, async (context) => {
    const page = await context.newPage();
    attachErrorCollectors(page, "12_capture_wizard_step1");
    await gotoPage(page, url);

    await waitForStep(page, "Identity");
    await populateWizard(page, knownDuplicate);
    await recordCapture(page, {
      name: "12_capture_wizard_step1",
      components: ["nav", "breadcrumb", "capture-wizard", "capture-step-identity"],
      notes: "Capture wizard step 1 with identity fields populated.",
    });

    await page.getByRole("button", { name: "Next" }).click();
    await waitForStep(page, "Source");
    await fillIfPresent(page, 'input[placeholder="SAP, Salesforce, Legacy ERP…"]', knownDuplicate.source_system);
    await page.waitForTimeout(350);
    await recordCapture(page, {
      name: "13_capture_wizard_step2_autocomplete",
      components: ["capture-wizard", "capture-step-source", "system-autocomplete"],
      notes: "Source-system autocomplete open with live suggestions.",
    });

    const sourceSuggestion = page.locator("div.absolute button").first();
    if (await sourceSuggestion.count()) {
      await sourceSuggestion.click();
    }
    await fillIfPresent(page, 'input[placeholder="REST, JDBC, FTP, SOAP…"]', knownDuplicate.source_technology ?? "REST");
    await fillIfPresent(page, 'input[placeholder="/api/v1/orders or reference URL"]', knownDuplicate.source_api_reference ?? "/audit/source");
    await fillIfPresent(page, 'input[placeholder="Team or owner"]', knownDuplicate.source_owner ?? "Finance Platforms");
    await page.getByRole("button", { name: "Next" }).click();
    await waitForStep(page, "Destination");

    await fillIfPresent(page, 'input[placeholder="Oracle, WMS, Data Lake…"]', knownDuplicate.destination_system);
    await page.waitForTimeout(350);
    const destinationSuggestion = page.locator("div.absolute button").first();
    if (await destinationSuggestion.count()) {
      await destinationSuggestion.click();
    }
    await fillIfPresent(
      page,
      'input[placeholder="REST, ATP, SOAP…"]',
      knownDuplicate.destination_technology ?? knownDuplicate.destination_technology_1 ?? "REST",
    );
    await fillIfPresent(page, 'input[placeholder="Receiving team or owner"]', knownDuplicate.destination_owner ?? "Digital Marketing");
    await page.waitForTimeout(800);
    await recordCapture(page, {
      name: "14_capture_wizard_step3_duplicates",
      components: ["capture-wizard", "capture-step-destination", "system-autocomplete"],
      notes: "Destination step with duplicate-check state exposed.",
    });

    await page.getByRole("button", { name: "Next" }).click();
    await waitForStep(page, "Technical");
    const selects = page.locator("select");
    if (await selects.count()) {
      if ((await selects.count()) >= 1) {
        const triggerOptions = await selects.nth(0).locator("option").allTextContents();
        const triggerTarget =
          triggerOptions.find((text) => /rest|event|trigger/i.test(text) && !/select/i.test(text)) ??
          triggerOptions[1];
        if (triggerTarget) {
          await selects.nth(0).selectOption({ label: triggerTarget.trim() }).catch(() => {});
        }
      }
      if ((await selects.count()) >= 2) {
        const frequencyOptions = await selects.nth(1).locator("option").allTextContents();
        const frequencyTarget =
          frequencyOptions.find((text) => text.includes(knownDuplicate.frequency ?? "")) ??
          frequencyOptions.find((text) => /Tiempo Real|Cada 5 minutos/i.test(text)) ??
          frequencyOptions[1];
        if (frequencyTarget) {
          await selects.nth(1).selectOption({ label: frequencyTarget.trim() }).catch(() => {});
        }
      }
      if ((await selects.count()) >= 3) {
        const complexityOptions = await selects.nth(2).locator("option").allTextContents();
        const complexityTarget =
          complexityOptions.find((text) => text.includes(knownDuplicate.complexity ?? "")) ??
          complexityOptions.find((text) => /Bajo|Medio|Alto/i.test(text)) ??
          complexityOptions[1];
        if (complexityTarget) {
          await selects.nth(2).selectOption({ label: complexityTarget.trim() }).catch(() => {});
        }
      }
      if ((await selects.count()) >= 4) {
        const patternOptions = await selects.nth(3).locator("option").allTextContents();
        const patternTarget =
          patternOptions.find((text) => text.includes("#01")) ??
          patternOptions[1];
        if (patternTarget) {
          await selects.nth(3).selectOption({ label: patternTarget.trim() }).catch(() => {});
        }
      }
    }
    await fillIfPresent(page, 'input[placeholder="0.0"]', "50");
    await fillIfPresent(page, 'input[placeholder="Resolved, TBD, medium confidence…"]', "TBD");
    await fillIfPresent(page, 'textarea[placeholder="Why is this the best fit for the integration?"]', "Audit-only coverage rationale for preview components.");
    const toolCheckbox = page.locator('input[type="checkbox"]').first();
    if (await toolCheckbox.count()) {
      await toolCheckbox.check().catch(() => {});
    }
    await page.waitForTimeout(1200);
    await recordCapture(page, {
      name: "15_capture_wizard_step4_previews",
      components: [
        "capture-wizard",
        "capture-step-technical",
        "oic-estimate-preview",
        "qa-preview",
        "pattern-support-badge",
      ],
      notes: "Technical step with live OIC estimate and QA preview components populated.",
    });

    await page.getByRole("button", { name: "Next" }).click();
    await waitForStep(page, "Review");
    await recordCapture(page, {
      name: "16_capture_wizard_step5_review",
      components: ["capture-wizard", "capture-step-review"],
      notes: "Capture wizard review step before submit.",
    });
  });
}

async function captureCaptureLanding(browser, projectId) {
  const url = `${BASE_URL}/projects/${projectId}/capture`;

  await captureRoute(browser, {
    name: "17_capture_landing",
    url,
    components: ["nav", "breadcrumb", "capture-history-client"],
    notes: "Capture landing with recent guided captures.",
  });

  await captureRoute(browser, {
    name: "18_capture_remove_modal",
    url,
    components: ["capture-history-client", "modal"],
    notes: "Removal ConfirmModal opened from capture history.",
    afterGoto: async (page) => {
      const removeButton = page.getByRole("button", { name: "Remove" }).first();
      if (await removeButton.count()) {
        await removeButton.click();
        await delay(250);
      }
    },
  });
}

async function captureCatalog(browser, projectId, integrationId) {
  const url = `${BASE_URL}/projects/${projectId}/catalog`;

  await captureRoute(browser, {
    name: "19_catalog_baseline",
    url,
    components: ["nav", "breadcrumb", "catalog-table", "pattern-badge", "complexity-badge", "qa-badge"],
    notes: "Catalog baseline at desktop width.",
  });

  await captureRoute(browser, {
    name: "20_catalog_filtered",
    url,
    components: ["catalog-table", "pattern-badge", "complexity-badge", "qa-badge"],
    notes: "Catalog with active text and QA filters.",
    afterGoto: async (page) => {
      await fillIfPresent(page, 'input[placeholder="Interface, system, description..."]', "SAP");
      const qaSelect = page.locator("select").nth(0);
      if (await qaSelect.count()) {
        await qaSelect.selectOption("REVISAR").catch(() => {});
      }
      await delay(800);
    },
  });

  await captureRoute(browser, {
    name: "21_catalog_empty_state",
    url,
    components: ["catalog-table"],
    notes: "Catalog empty state using an impossible search term.",
    afterGoto: async (page) => {
      await fillIfPresent(page, 'input[placeholder="Interface, system, description..."]', "ZZZZZZ_AUDIT_NO_MATCH");
      await delay(800);
    },
  });

  await withContext(browser, { viewport: { width: 1440, height: 980 }, theme: "light" }, async (context) => {
    await context.route(`**/api/v1/catalog/${projectId}**`, async (route) => {
      await delay(3500);
      await route.continue();
    });
    const page = await context.newPage();
    attachErrorCollectors(page, "22_catalog_loading_skeleton");
    await gotoPage(page, url, "domcontentloaded");
    await delay(700);
    await recordCapture(page, {
      name: "22_catalog_loading_skeleton",
      components: ["catalog-table", "skeleton"],
      notes: "Catalog loading state with delayed client refresh to expose skeleton rows.",
      viewport: { width: 1440, height: 980 },
    });
  });

  await captureRoute(browser, {
    name: "23_catalog_mobile",
    url,
    viewport: { width: 390, height: 844 },
    components: ["catalog-table", "pattern-badge", "complexity-badge", "qa-badge"],
    notes: "Catalog mobile layout.",
  });

  await captureRoute(browser, {
    name: "24_catalog_dark",
    url,
    theme: "dark",
    components: ["catalog-table", "pattern-badge", "complexity-badge", "qa-badge"],
    notes: "Catalog dark theme.",
  });

  if (integrationId) {
    await captureRoute(browser, {
      name: "25_catalog_row_edit_affordance",
      url,
      components: ["catalog-table"],
      notes: "Catalog row action affordance visible before opening integration detail.",
      fullPage: false,
      afterGoto: async (page) => {
        const editButton = page.locator('button[title="Edit pattern"]:visible').first();
        if (await editButton.count()) {
          await editButton.scrollIntoViewIfNeeded();
          await delay(200);
        }
      },
    });
  }
}

async function captureIntegrationDetail(browser, projectId, integrationId) {
  const url = `${BASE_URL}/projects/${projectId}/catalog/${integrationId}`;

  await captureRoute(browser, {
    name: "26_integration_detail_top",
    url,
    components: ["nav", "breadcrumb", "qa-badge", "integration-patch-form"],
    notes: "Integration detail top section with source data and patch form visible.",
  });

  await captureRoute(browser, {
    name: "27_integration_patch_form",
    url,
    components: ["integration-patch-form", "pattern-badge", "pattern-support-badge", "qa-badge"],
    notes: "Patch form close-up including current pattern, support badge, and actions.",
    fullPage: false,
    afterGoto: async (page) => {
      await page.locator("#patch-form").scrollIntoViewIfNeeded();
      await delay(150);
    },
  });

  await captureRoute(browser, {
    name: "28_integration_remove_modal",
    url,
    components: ["integration-patch-form", "modal"],
    notes: "Integration removal ConfirmModal opened without confirming.",
    afterGoto: async (page) => {
      await page.locator("#patch-form").scrollIntoViewIfNeeded();
      await page.getByRole("button", { name: "Remove Integration" }).click();
      await delay(250);
    },
  });

  await captureRoute(browser, {
    name: "29_integration_canvas_baseline",
    url,
    components: ["integration-design-canvas-panel", "integration-canvas", "pattern-support-badge"],
    notes: "Integration design canvas baseline with palette, route, and governance summary.",
    afterGoto: async (page) => {
      await page.getByText("Integration Design Canvas").scrollIntoViewIfNeeded();
      await delay(200);
    },
  });

  await captureRoute(browser, {
    name: "30_integration_canvas_selected_node",
    url,
    components: ["integration-design-canvas-panel", "integration-canvas"],
    notes: "Canvas after selecting the first editable node to expose handles and inline actions.",
    afterGoto: async (page) => {
      await page.getByText("Integration Design Canvas").scrollIntoViewIfNeeded();
      await delay(250);
      const box = await page.evaluate(() => {
        const candidate = [...document.querySelectorAll("svg rect")]
          .map((element) => ({ element, width: Number(element.getAttribute("width") ?? "0") }))
          .find((entry) => entry.width === 208);
        if (!candidate) {
          return null;
        }
        const rect = candidate.element.getBoundingClientRect();
        return {
          x: rect.left + rect.width / 2,
          y: rect.top + rect.height / 2,
        };
      });
      if (box) {
        await page.mouse.click(box.x, box.y);
        await delay(300);
      }
    },
  });

  await captureRoute(browser, {
    name: "31_integration_lineage_raw_values",
    url,
    components: ["raw-column-values-table", "truncated-cell"],
    notes: "Lower detail surface with source lineage and raw-column-values table.",
    afterGoto: async (page) => {
      await page.getByText("Raw Column Values").scrollIntoViewIfNeeded();
      await delay(200);
      const showFullButton = page.getByRole("button", { name: "Show full" }).first();
      if (await showFullButton.count()) {
        await showFullButton.click();
        await delay(150);
      }
    },
  });

  await captureRoute(browser, {
    name: "32_integration_dark",
    url,
    theme: "dark",
    components: ["integration-patch-form", "integration-design-canvas-panel", "integration-canvas"],
    notes: "Integration detail in dark theme.",
  });

  await captureRoute(browser, {
    name: "33_integration_mobile",
    url,
    viewport: { width: 390, height: 844 },
    components: ["integration-patch-form", "integration-design-canvas-panel"],
    notes: "Integration detail mobile layout.",
  });
}

async function captureGraph(browser, projectId) {
  const url = `${BASE_URL}/projects/${projectId}/graph`;

  await captureRoute(browser, {
    name: "34_graph_baseline",
    url,
    components: ["nav", "breadcrumb", "graph-controls", "graph-export-button", "integration-graph", "graph-detail-panel"],
    notes: "Graph baseline with controls, export affordance, and empty detail panel.",
    afterGoto: async (page) => {
      await page.waitForTimeout(1800);
    },
  });

  await captureRoute(browser, {
    name: "35_graph_node_selected",
    url,
    components: ["integration-graph", "graph-detail-panel"],
    notes: "Graph after selecting the first node to expose system detail panel.",
    afterGoto: async (page) => {
      await page.waitForTimeout(1800);
      const node = page.locator("svg circle").first();
      if (await node.count()) {
        await node.click();
        await delay(400);
      }
    },
  });

  await captureRoute(browser, {
    name: "36_graph_edge_selected",
    url,
    components: ["integration-graph", "graph-detail-panel"],
    notes: "Graph after selecting the first edge to expose relationship detail panel.",
    afterGoto: async (page) => {
      await page.waitForTimeout(1800);
      const clicked = await page.evaluate(() => {
        const edge = document.querySelector("svg line[marker-end]");
        if (!edge) {
          return false;
        }
        edge.dispatchEvent(
          new MouseEvent("click", {
            bubbles: true,
            cancelable: true,
            composed: true,
          }),
        );
        return true;
      });
      if (clicked) {
        await delay(400);
      }
    },
  });

  await captureRoute(browser, {
    name: "37_graph_system_filter",
    url,
    components: ["graph-controls", "integration-graph", "graph-detail-panel"],
    notes: "Graph with system filter applied.",
    afterGoto: async (page) => {
      await page.waitForTimeout(1800);
      const systemSelect = page.locator("select").nth(3);
      if (await systemSelect.count()) {
        const options = await systemSelect.locator("option").allTextContents();
        const target = options.find((option) => option && option !== "All");
        if (target) {
          await systemSelect.selectOption({ label: target });
          await delay(500);
        }
      }
    },
  });

  await captureRoute(browser, {
    name: "38_graph_mobile_fallback",
    url,
    viewport: { width: 390, height: 844 },
    components: ["graph-controls", "graph-detail-panel"],
    notes: "Graph mobile fallback message on small screens.",
    afterGoto: async (page) => {
      await page.waitForTimeout(1200);
    },
  });

  await captureRoute(browser, {
    name: "39_graph_dark",
    url,
    theme: "dark",
    components: ["graph-controls", "graph-export-button", "integration-graph", "graph-detail-panel"],
    notes: "Graph in dark theme.",
    afterGoto: async (page) => {
      await page.waitForTimeout(1800);
    },
  });
}

async function captureNotFound(browser) {
  await captureRoute(browser, {
    name: "40_project_not_found",
    url: `${BASE_URL}/projects/00000000-0000-0000-0000-000000000000`,
    components: ["nav", "breadcrumb"],
    notes: "Graceful invalid-project not-found surface.",
  });
}

async function captureAdmin(browser, versions, dictionaryCategory, syntheticNormalJobId, syntheticErrorJobId) {
  await captureRoute(browser, {
    name: "41_admin_hub",
    url: `${BASE_URL}/admin`,
    components: ["nav", "breadcrumb"],
    notes: "Admin governance hub.",
  });

  await captureRoute(browser, {
    name: "42_admin_patterns_baseline",
    url: `${BASE_URL}/admin/patterns`,
    components: ["nav", "breadcrumb", "pattern-support-badge"],
    notes: "Admin patterns baseline table.",
  });

  await captureRoute(browser, {
    name: "43_admin_pattern_form",
    url: `${BASE_URL}/admin/patterns`,
    components: ["admin-pattern-form"],
    notes: "Pattern create form open.",
    afterGoto: async (page) => {
      await page.getByRole("button", { name: "New Pattern" }).click();
      await delay(250);
    },
  });

  await captureRoute(browser, {
    name: "44_admin_pattern_delete_modal",
    url: `${BASE_URL}/admin/patterns`,
    components: ["admin-confirm-delete"],
    notes: "Admin delete confirmation modal from patterns.",
    afterGoto: async (page) => {
      const deleteButton = page.getByRole("button", { name: /Delete/i }).first();
      if (await deleteButton.count()) {
        await deleteButton.click();
        await delay(250);
      }
    },
  });

  await captureRoute(browser, {
    name: "45_admin_assumptions_baseline",
    url: `${BASE_URL}/admin/assumptions`,
    components: ["breadcrumb"],
    notes: "Assumptions overview table baseline.",
  });

  await captureRoute(browser, {
    name: "46_admin_assumption_form",
    url: `${BASE_URL}/admin/assumptions`,
    components: ["admin-assumption-form"],
    notes: "Assumption create/clone form open.",
    afterGoto: async (page) => {
      await page.getByRole("button", { name: "New Version" }).click();
      await delay(250);
    },
  });

  if (versions.default) {
    await captureRoute(browser, {
      name: "47_admin_assumption_detail_default",
      url: `${BASE_URL}/admin/assumptions/${versions.default}`,
      components: ["breadcrumb"],
      notes: "Default assumption version detail page.",
    });
  }

  if (versions.nonDefault) {
    await captureRoute(browser, {
      name: "48_admin_assumption_detail_nondefault",
      url: `${BASE_URL}/admin/assumptions/${versions.nonDefault}`,
      components: ["breadcrumb"],
      notes: "Non-default assumption version detail page with alternate action state.",
    });
  }

  await captureRoute(browser, {
    name: "49_admin_dictionaries_overview",
    url: `${BASE_URL}/admin/dictionaries`,
    components: ["breadcrumb"],
    notes: "Dictionary categories overview.",
  });

  await captureRoute(browser, {
    name: "50_admin_dictionary_category_baseline",
    url: `${BASE_URL}/admin/dictionaries/${dictionaryCategory}`,
    components: ["breadcrumb"],
    notes: "Dictionary category baseline table.",
  });

  await captureRoute(browser, {
    name: "51_admin_dictionary_form_create",
    url: `${BASE_URL}/admin/dictionaries/${dictionaryCategory}`,
    components: ["admin-dictionary-form"],
    notes: "Dictionary create form open.",
    afterGoto: async (page) => {
      await page.getByRole("button", { name: "New Option" }).click();
      await delay(250);
    },
  });

  await captureRoute(browser, {
    name: "52_admin_dictionary_form_edit",
    url: `${BASE_URL}/admin/dictionaries/${dictionaryCategory}`,
    components: ["admin-dictionary-form"],
    notes: "Dictionary edit form open.",
    afterGoto: async (page) => {
      const editButton = page.getByRole("button", { name: /Edit/i }).first();
      if (await editButton.count()) {
        await editButton.click();
        await delay(250);
      }
    },
  });

  await captureRoute(browser, {
    name: "53_admin_dictionary_delete_modal",
    url: `${BASE_URL}/admin/dictionaries/${dictionaryCategory}`,
    components: ["admin-confirm-delete"],
    notes: "Admin delete confirmation modal from dictionary category.",
    afterGoto: async (page) => {
      const deleteButton = page.getByRole("button", { name: /Delete/i }).first();
      if (await deleteButton.count()) {
        await deleteButton.click();
        await delay(250);
      }
    },
  });

  await captureRoute(browser, {
    name: "54_admin_synthetic_lab",
    url: `${BASE_URL}/admin/synthetic`,
    components: ["breadcrumb"],
    notes: "Synthetic Lab baseline with job submission form and recent jobs.",
  });

  if (syntheticNormalJobId) {
    await captureRoute(browser, {
      name: "55_admin_synthetic_job_normal",
      url: `${BASE_URL}/admin/synthetic/${syntheticNormalJobId}`,
      components: ["breadcrumb"],
      notes: "Synthetic job detail page in normal cleaned-up state.",
    });
  }

  if (syntheticErrorJobId) {
    await captureRoute(browser, {
      name: "56_admin_synthetic_job_error",
      url: `${BASE_URL}/admin/synthetic/${syntheticErrorJobId}`,
      components: ["breadcrumb"],
      notes: "Synthetic job detail page with diagnostics/error details visible.",
    });
  }
}

async function resolveDynamicIds() {
  const projects = await fetchJson(`${API_URL}/projects/`);
  const project =
    projects.projects.find((entry) => entry.name.includes("NovaBrand")) ??
    projects.projects[0];
  if (!project) {
    throw new Error("No projects available for audit.");
  }

  const catalog = await fetchJson(`${API_URL}/catalog/${project.id}?page=1&page_size=5`);
  const integration = catalog.integrations[0];
  if (!integration) {
    throw new Error(`No catalog integrations available for project ${project.id}.`);
  }

  const imports = await fetchJson(`${API_URL}/imports/${project.id}?limit=5`);
  const importBatches = imports.batches ?? imports.import_batches ?? [];
  const importBatch = importBatches[0] ?? null;

  const assumptions = await fetchJson(`${API_URL}/assumptions/`);
  const defaultAssumption =
    assumptions.assumption_sets.find((entry) => entry.is_default)?.version ??
    assumptions.assumption_sets[0]?.version ??
    null;
  const nonDefaultAssumption =
    assumptions.assumption_sets.find((entry) => !entry.is_default)?.version ?? null;

  const dictionaries = await fetchJson(`${API_URL}/dictionaries/`);
  const dictionaryCategory =
    dictionaries.categories.find((entry) => entry.category === "FREQUENCY")?.category ??
    dictionaries.categories[0]?.category ??
    "FREQUENCY";

  const syntheticJobs = await fetchJson(`${API_URL}/admin/synthetic/jobs?limit=20`, {
    headers: {
      "X-Actor-Id": "web-admin",
      "X-Actor-Role": "Admin",
    },
  });
  const normalSyntheticJob =
    syntheticJobs.jobs.find((entry) => entry.error_details === null) ?? syntheticJobs.jobs[0] ?? null;
  const errorSyntheticJob =
    syntheticJobs.jobs.find((entry) => entry.error_details !== null) ?? null;

  manifest.project = project;
  manifest.dynamic_ids = {
    project_id: project.id,
    integration_id: integration.id,
    import_batch_id: importBatch?.id ?? null,
    assumption_default: defaultAssumption,
    assumption_non_default: nonDefaultAssumption,
    dictionary_category: dictionaryCategory,
    synthetic_job_normal: normalSyntheticJob?.id ?? null,
    synthetic_job_error: errorSyntheticJob?.id ?? null,
  };

  return {
    project,
    integration,
    importBatchId: importBatch?.id ?? null,
    versions: {
      default: defaultAssumption,
      nonDefault: nonDefaultAssumption,
    },
    dictionaryCategory,
    syntheticNormalJobId: normalSyntheticJob?.id ?? null,
    syntheticErrorJobId: errorSyntheticJob?.id ?? null,
  };
}

function finalizeCoverage() {
  const covered = new Set(manifest.captures.flatMap((capture) => capture.components));
  manifest.coverage.covered = [...covered].sort();
  manifest.coverage.missing = COMPONENT_INVENTORY.filter((component) => !covered.has(component));
}

async function writeManifest() {
  finalizeCoverage();
  await fs.writeFile(MANIFEST_PATH, `${JSON.stringify(manifest, null, 2)}\n`, "utf8");
}

async function run() {
  await ensureDirs();
  const resolved = await resolveDynamicIds();
  const browser = await chromium.launch({ headless: true });
  const runStep = async (label, fn) => {
    try {
      await fn();
    } catch (error) {
      manifest.failures.push({
        step: label,
        error: String(error),
      });
      console.error(`Step failed: ${label}`);
      console.error(error);
    }
  };

  try {
    await runStep("projects", async () => captureProjects(browser, resolved.project));
    await runStep("dashboard", async () => captureDashboard(browser, resolved.project.id));
    await runStep("import", async () => captureImport(browser, resolved.project.id, resolved.importBatchId));
    await runStep("capture-landing", async () => captureCaptureLanding(browser, resolved.project.id));
    await runStep("capture-wizard", async () => captureCaptureWizard(browser, resolved.project.id, resolved.integration));
    await runStep("catalog", async () => captureCatalog(browser, resolved.project.id, resolved.integration.id));
    await runStep("integration-detail", async () => captureIntegrationDetail(browser, resolved.project.id, resolved.integration.id));
    await runStep("graph", async () => captureGraph(browser, resolved.project.id));
    await runStep("not-found", async () => captureNotFound(browser));
    await runStep("admin", async () =>
      captureAdmin(
        browser,
        resolved.versions,
        resolved.dictionaryCategory,
        resolved.syntheticNormalJobId,
        resolved.syntheticErrorJobId,
      ),
    );
  } catch (error) {
    manifest.failures.push(String(error));
    throw error;
  } finally {
    await browser.close();
    await writeManifest();
  }

  const total = manifest.captures.length;
  const missing = manifest.coverage.missing.length;
  console.log(`Audit complete: ${total} screenshots.`);
  console.log(`Missing component coverage: ${missing}`);
  if (missing > 0) {
    console.log(manifest.coverage.missing.join(", "));
  }
  console.log(`Manifest: ${MANIFEST_PATH}`);
}

run().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
