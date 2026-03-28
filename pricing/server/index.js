'use strict';

const express = require('express');
const path    = require('path');
const https   = require('https');
const fs      = require('fs');
const { normalizeCatalog, searchProducts, searchPresets, searchServiceRegistry } = require('./catalog');
const { quoteFromPrompt, buildQuote } = require('./quotation-engine');
const { parseWorkbookBase64, workbookToRequests } = require('./excel');
const { loadGenAISettings, runChat, extractChatText } = require('./genai');
const { respondToAssistant } = require('./assistant');

const app  = express();
const PORT = process.env.PORT || 8742;

app.use(express.json({ limit: '25mb' }));

// ════════════════════════════════════════════════════════════
//  OCI GenAI — Config from environment
// ════════════════════════════════════════════════════════════
function loadOciConfig() {
  const genai = loadGenAISettings(process.env);
  const user        = process.env.OCI_USER        || '';
  const tenancy     = process.env.OCI_TENANCY      || '';
  const fingerprint = process.env.OCI_FINGERPRINT  || '';
  const region      = genai.region || process.env.OCI_REGION || 'us-chicago-1';
  const compartment = genai.compartmentId || process.env.OCI_COMPARTMENT || tenancy;
  const modelId     = genai.modelId || process.env.OCI_GENAI_MODEL ||
    'ocid1.generativeaimodel.oc1.us-chicago-1.amaaaaaask7dceyafjcwpf75fmqoismvwlmzjbprdzzljhfcrirozftbrjoq';
  const endpoint    = genai.endpoint;
  const profile     = genai.profile;

  let privateKeyPem = '';
  const keyContent = process.env.OCI_PRIVATE_KEY || '';
  const keyContentB64 = process.env.OCI_PRIVATE_KEY_B64 || '';
  const keyPath    = process.env.OCI_KEY_FILE    || '';
  if (keyContentB64) {
    try { privateKeyPem = Buffer.from(keyContentB64, 'base64').toString('utf8'); }
    catch(e) { console.warn('OCI_PRIVATE_KEY_B64 decode failed:', e.message); }
  } else if (keyContent) {
    privateKeyPem = keyContent.replace(/\\n/g, '\n');
  }
  else if (keyPath) {
    try { privateKeyPem = fs.readFileSync(keyPath, 'utf8'); }
    catch(e) { console.warn('OCI_KEY_FILE not readable:', e.message); }
  }

  const ok = !!(user && tenancy && fingerprint && privateKeyPem);
  return { user, tenancy, fingerprint, region, compartment, modelId, endpoint, profile, privateKeyPem, ok };
}

const WORKBOOK_ENRICHMENT_PROMPT = [
  'You are enriching an OCI workbook estimation response that was already calculated deterministically.',
  'Do not change any totals, numbers, SKUs, warnings, or assumptions.',
  'Do not invent migration facts.',
  'Do not restate counts, totals, or arithmetic from the workbook summary.',
  'Write concise markdown with the tone of an OCI VMware migration specialist.',
  'Only describe the workbook as RVTools or VMware inventory if the provided source type says so.',
  'If the source type is a generic inventory workbook, do not call it RVTools.',
  'Return:',
  '- OCI migration notes if the workbook clearly looks like RVTools or VMware inventory',
  '- OCI next checks if there are warnings that imply follow-up work',
].join('\n');

function sanitizeWorkbookEnrichment(text) {
  const source = String(text || '').trim();
  if (!source) return '';
  const lines = source.split('\n');
  const kept = [];
  let activeSection = '';
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) {
      if (kept.length && kept[kept.length - 1] !== '') kept.push('');
      continue;
    }
    if (/^#{1,6}\s+/i.test(trimmed)) {
      if (/migration notes/i.test(trimmed)) {
        activeSection = 'migration';
        kept.push('## OCI Migration Notes');
      } else if (/next checks/i.test(trimmed)) {
        activeSection = 'next-checks';
        kept.push('## OCI Next Checks');
      } else {
        activeSection = '';
      }
      continue;
    }
    if (!activeSection) continue;
    if (/\$|estimated monthly|estimated annual|processed .* into|count|total|vms?\b/i.test(trimmed)) continue;
    kept.push(line);
  }
  return kept.join('\n').trim();
}

function buildWorkbookFallbackSummary({ fileName, requests, warnings, totals }) {
  const currencyCode = totals?.currencyCode || 'USD';
  const requestCount = Array.isArray(requests) ? requests.length : 0;
  const sourceType = Array.isArray(requests) && requests.some((item) => item?.metadata?.inventorySource === 'rvtools')
    ? 'rvtools'
    : Array.isArray(requests) && requests.some((item) => item?.metadata?.inventorySource === 'inventory_workbook')
      ? 'inventory_workbook'
      : 'generic_workbook';
  const isRvTools = sourceType === 'rvtools';
  const isInventoryWorkbook = sourceType === 'inventory_workbook';
  const dominantShapes = Array.isArray(requests)
    ? Array.from(new Set(requests.map((item) => item?.shapeSeries).filter(Boolean))).slice(0, 3)
    : [];
  const lines = [
    `## OCI Expert Summary`,
    `- Processed \`${fileName}\` into ${requestCount} OCI-native sizing request${requestCount === 1 ? '' : 's'}.`,
    `- Estimated monthly total: ${formatMoney(totals?.monthly || 0, currencyCode)}.`,
    `- Estimated annual total: ${formatMoney(totals?.annual || 0, currencyCode)}.`,
  ];
  if (dominantShapes.length) {
    lines.push(`- Dominant OCI compute profiles inferred: ${dominantShapes.map((item) => `\`${item}\``).join(', ')}.`);
  }
  if (isRvTools) {
    lines.push('');
    lines.push('## OCI Migration Notes');
    lines.push('- This workbook was treated as VMware inventory and mapped to OCI compute plus block storage sizing.');
    lines.push('- For x86 VMs, the import uses `2 VMware vCPUs = 1 OCI OCPU`.');
    lines.push('- This is infrastructure sizing guidance; application compatibility, VMware platform services, and OS licensing still need migration review.');
  } else if (isInventoryWorkbook) {
    lines.push('');
    lines.push('## OCI Migration Notes');
    lines.push('- This workbook was treated as a structured infrastructure inventory and mapped heuristically to OCI-native compute plus block storage sizing.');
    lines.push('- Validate the inferred OCI shape family and operating-system-specific licensing before using the estimate as a migration baseline.');
  }
  if (Array.isArray(warnings) && warnings.length) {
    lines.push('');
    lines.push('## OCI Next Checks');
    lines.push(...warnings.slice(0, 3).map((item) => `- ${item}`));
  }
  return lines.join('\n');
}

async function buildWorkbookEnrichment(cfg, { fileName, requests, warnings, totals, lineItems }) {
  const fallback = buildWorkbookFallbackSummary({ fileName, requests, warnings, totals });
  const sourceType = Array.isArray(requests) && requests.some((item) => item?.metadata?.inventorySource === 'rvtools')
    ? 'rvtools'
    : Array.isArray(requests) && requests.some((item) => item?.metadata?.inventorySource === 'inventory_workbook')
      ? 'inventory_workbook'
      : 'generic_workbook';
  if (!cfg?.ok || !Array.isArray(lineItems) || !lineItems.length) return fallback;
  if (sourceType !== 'rvtools') return fallback;
  const currencyCode = totals?.currencyCode || 'USD';
  const requestCount = Array.isArray(requests) ? requests.length : 0;
  const contextBlock = [
    `Workbook: ${fileName}`,
    'Expert role: OCI VMware migration specialist',
    `Source type: ${sourceType}`,
    `Requests detected: ${requestCount}`,
    `Monthly total: ${formatMoney(totals?.monthly || 0, currencyCode)}`,
    `Annual total: ${formatMoney(totals?.annual || 0, currencyCode)}`,
    `Warnings:\n${(warnings || []).slice(0, 6).map((item) => `- ${item}`).join('\n')}`,
    `Representative OCI lines:\n${lineItems.slice(0, 10).map((line) => `- ${line.service || '-'} | ${line.product} | ${line.metric || '-'} | monthly ${formatMoney(line.monthly, currencyCode)}`).join('\n')}`,
  ].filter(Boolean).join('\n\n');

  try {
    const response = await runChat({
      cfg,
      systemPrompt: WORKBOOK_ENRICHMENT_PROMPT,
      messages: [{ role: 'user', content: contextBlock }],
      maxTokens: 450,
      temperature: 0.2,
      topP: 0.6,
      topK: -1,
    });
    const enrichment = sanitizeWorkbookEnrichment(extractChatText(response?.data || response).trim());
    return enrichment ? `${fallback}\n\n${enrichment}` : fallback;
  } catch (_error) {
    return fallback;
  }
}

function formatMoney(value, currencyCode = 'USD') {
  const num = Number(value);
  if (!Number.isFinite(num)) return `${currencyCode} -`;
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: currencyCode,
    minimumFractionDigits: 2,
    maximumFractionDigits: 4,
  }).format(num);
}

// ════════════════════════════════════════════════════════════
//  POST /api/chat  — OCI GenAI only
// ════════════════════════════════════════════════════════════
app.post('/api/chat', async (req, res) => {
  const cfg = loadOciConfig();
  if (!cfg.ok) {
    return res.status(500).json({
      type: 'error',
      error: {
        type: 'configuration_error',
        message: 'OCI GenAI is not configured. Set OCI_USER, OCI_TENANCY, OCI_FINGERPRINT and OCI_PRIVATE_KEY in your .env file.',
      }
    });
  }
  try {
    const response = await runChat({
      cfg,
      systemPrompt: req.body.system || '',
      messages: req.body.messages || [],
      maxTokens: req.body.max_tokens || 2000,
    });
    const payload = response && response.data ? response.data : response;
    const text = extractChatText(payload);
    return res.json({
      id: 'oci-' + Date.now(),
      type: 'message',
      role: 'assistant',
      content: [{ type: 'text', text: text || '' }],
      model: cfg.modelId,
      stop_reason: 'end_turn',
      raw: text ? undefined : payload,
    });
  } catch (err) {
    const status = Number(err?.status || err?.statusCode || 502);
    return res.status(Number.isFinite(status) ? status : 502).json({
      type: 'error',
      error: {
        type: 'oci_genai_error',
        message: err?.message || 'OCI GenAI request failed.',
        status: Number.isFinite(status) ? status : undefined,
        details: err.message,
      }
    });
  }
});

app.post('/api/assistant', async (req, res) => {
  if (!ensureCatalogReady(res)) return;
  const cfg = loadOciConfig();
  if (!cfg.ok) {
    return res.status(500).json({
      ok: false,
      error: 'OCI GenAI is not configured.',
    });
  }
  const text = String(req.body.text || '').trim();
  const conversation = Array.isArray(req.body.conversation) ? req.body.conversation : [];
  const imageDataUrl = String(req.body.imageDataUrl || '').trim();
  if (!text && !imageDataUrl) return res.status(400).json({ ok: false, error: 'Provide text or imageDataUrl.' });

  try {
    const reply = await respondToAssistant({
      cfg,
      index: store.normalized,
      conversation,
      userText: text,
      imageDataUrl,
    });
    return res.json(reply);
  } catch (error) {
    return res.status(502).json({
      ok: false,
      error: error.message || 'Assistant request failed.',
    });
  }
});

// ── Config status ──────────────────────────────────────────
app.get('/api/providers', (_req, res) => {
  const cfg = loadOciConfig();
  res.json({ oci: { configured: cfg.ok, region: cfg.region, endpoint: cfg.endpoint, compartment: cfg.compartment, modelId: cfg.modelId, profile: cfg.profile } });
});

// ════════════════════════════════════════════════════════════
//  OCI Catalog download
// ════════════════════════════════════════════════════════════
const OCI_URLS = {
  'products.json':       'https://www.oracle.com/a/ocom/docs/cloudestimator2/data/products.json',
  'productpresets.json': 'https://www.oracle.com/a/ocom/docs/cloudestimator2/data/productpresets.json',
  'metrics.json':        'https://www.oracle.com/a/ocom/docs/cloudestimator2/data/metrics.json',
};

const FRONTEND_DIR = path.join(__dirname, '..', 'app');
const CACHE_TTL_MS = 6 * 60 * 60 * 1000;
const store = { data: {}, loadedAt: {}, errors: {}, busy: false, normalized: null };

function fetchJSON(url, hops = 5) {
  return new Promise((resolve, reject) => {
    if (hops < 0) return reject(new Error('Too many redirects'));
    const req = https.get(url, {
      headers: { 'User-Agent': 'Mozilla/5.0 (compatible; OCI-Pricing-Agent/2.1)', 'Accept': 'application/json, */*' },
      timeout: 30000,
    }, (r) => {
      if (r.statusCode >= 300 && r.statusCode < 400 && r.headers.location) {
        r.resume(); return fetchJSON(r.headers.location, hops - 1).then(resolve).catch(reject);
      }
      if (r.statusCode !== 200) { r.resume(); return reject(new Error(`HTTP ${r.statusCode}`)); }
      const c = [];
      r.on('data', d => c.push(d));
      r.on('end', () => { try { resolve(JSON.parse(Buffer.concat(c).toString('utf8'))); } catch(e) { reject(e); } });
      r.on('error', reject);
    });
    req.on('error', reject);
    req.on('timeout', () => { req.destroy(); reject(new Error('Timeout')); });
  });
}

async function fetchOne(name) {
  console.log(`  ↓ ${name}…`);
  try {
    const data = await fetchJSON(OCI_URLS[name]);
    store.data[name] = data; store.loadedAt[name] = new Date(); delete store.errors[name];
    store.normalized = normalizeCatalog(store.data);
    const n = data?.items?.length ?? (Array.isArray(data) ? data.length : '?');
    console.log(`  ✓ ${name} (${n} entries)`);
  } catch(e) { store.errors[name] = e.message; console.warn(`  ✗ ${name} — ${e.message}`); }
}

async function fetchAll() {
  if (store.busy) return;
  store.busy = true;
  console.log('\n━━ Downloading OCI catalogs from oracle.com ━━');
  await Promise.all(Object.keys(OCI_URLS).map(fetchOne));
  store.busy = false;
  console.log(`\n${Object.keys(store.data).length}/${Object.keys(OCI_URLS).length} catalogs ready.\n`);
}

setInterval(() => {
  const now = Date.now();
  const stale = Object.keys(OCI_URLS).filter(n => { const t = store.loadedAt[n]; return !t || now - t.getTime() > CACHE_TTL_MS; });
  if (stale.length) { console.log(`↺ Auto-refresh: ${stale.join(', ')}`); Promise.all(stale.map(fetchOne)); }
}, 60 * 60 * 1000);

app.get('/api/health', (_req, res) => {
  const catalogs = {};
  for (const n of Object.keys(OCI_URLS)) catalogs[n] = { loaded: !!store.data[n], loadedAt: store.loadedAt[n] ?? null, error: store.errors[n] ?? null };
  const cfg = loadOciConfig();
  res.json({ ok: Object.keys(store.data).length > 0, catalogsLoaded: Object.keys(store.data).length, loading: store.busy, catalogs, ociConfigured: cfg.ok });
});

function ensureCatalogReady(res) {
  if (!store.normalized || !store.normalized.products.length) {
    res.status(503).json({ ok: false, error: 'OCI catalog is not ready yet.' });
    return false;
  }
  return true;
}

app.get('/api/catalog/search', (req, res) => {
  if (!ensureCatalogReady(res)) return;
  const q = String(req.query.q || '');
  res.json({
    ok: true,
    products: searchProducts(store.normalized, q, 15),
    presets: searchPresets(store.normalized, q, 10),
    services: searchServiceRegistry(store.normalized.serviceRegistry, q, 12),
  });
});

app.get('/api/coverage', (req, res) => {
  if (!ensureCatalogReady(res)) return;
  const q = String(req.query.q || '').trim();
  const registry = store.normalized.serviceRegistry || { services: [], summary: {} };
  const services = q ? searchServiceRegistry(registry, q, 50) : registry.services;
  res.json({
    ok: true,
    summary: registry.summary,
    services,
  });
});

app.get('/api/catalog/:file', (req, res) => {
  const { file } = req.params;
  if (!OCI_URLS[file]) return res.status(404).json({ error: 'Unknown catalog' });
  if (store.busy && !store.data[file]) return res.status(202).json({ error: 'Still loading', loading: true });
  if (!store.data[file]) return res.status(503).json({ error: store.errors[file] || 'Not available' });
  res.setHeader('Cache-Control', 'public, max-age=1800').json(store.data[file]);
});

app.post('/api/catalog/reload', (_req, res) => {
  Object.keys(store.data).forEach(k => { delete store.data[k]; delete store.loadedAt[k]; });
  store.normalized = null;
  fetchAll();
  res.json({ ok: true });
});

app.post('/api/quote', (req, res) => {
  if (!ensureCatalogReady(res)) return;
  const text = String(req.body.text || '');
  const lines = Array.isArray(req.body.lines) ? req.body.lines : [];

  if (!text && !lines.length) {
    return res.status(400).json({ ok: false, error: 'Provide text or structured lines.' });
  }

  if (text) return res.json(quoteFromPrompt(store.normalized, text));

  const results = lines.map((line) => buildQuote(store.normalized, line));
  const lineItems = results.flatMap((result) => result.lineItems || []);
  const warnings = results.flatMap((result) => result.warnings || []);
  const errors = results.filter((result) => !result.ok).map((result) => result.error);
  const totals = lineItems.reduce((acc, line) => {
    acc.monthly += line.monthly;
    acc.annual += line.annual;
    acc.currencyCode = line.currencyCode;
    return acc;
  }, { monthly: 0, annual: 0, currencyCode: 'USD' });

  return res.json({
    ok: !!lineItems.length,
    source: 'structured-lines',
    results,
    lineItems,
    warnings,
    errors,
    totals,
  });
});

app.post('/api/excel/estimate', async (req, res) => {
  if (!ensureCatalogReady(res)) return;
  const cfg = loadOciConfig();
  const fileName = String(req.body.fileName || 'workbook.xlsx');
  const contentBase64 = String(req.body.contentBase64 || '');
  if (!contentBase64) return res.status(400).json({ ok: false, error: 'Workbook contentBase64 is required.' });

  try {
    const workbook = parseWorkbookBase64(contentBase64);
    const { requests, warnings: workbookWarnings } = workbookToRequests(workbook);
    if (!requests.length) {
      return res.status(400).json({ ok: false, error: 'No quotable rows were detected in the workbook.' });
    }
    const results = requests.map((request) => buildQuote(store.normalized, request));
    const lineItems = results.flatMap((result) => result.lineItems || []);
    const warnings = [...(workbookWarnings || []), ...results.flatMap((result) => result.warnings || [])];
    const errors = results.filter((result) => !result.ok).map((result) => result.error);
    const totals = lineItems.reduce((acc, line) => {
      acc.monthly += line.monthly;
      acc.annual += line.annual;
      acc.currencyCode = line.currencyCode;
      return acc;
    }, { monthly: 0, annual: 0, currencyCode: 'USD' });
    const summary = await buildWorkbookEnrichment(cfg, {
      fileName,
      requests,
      warnings,
      totals,
      lineItems,
    });

    return res.json({
      ok: !!lineItems.length,
      source: 'excel',
      fileName,
      summary,
      requests,
      results,
      lineItems,
      warnings,
      errors,
      totals,
    });
  } catch (error) {
    return res.status(400).json({ ok: false, error: `Could not parse workbook: ${error.message}` });
  }
});

app.use(express.static(FRONTEND_DIR));
app.get('*', (_req, res) => res.sendFile(path.join(FRONTEND_DIR, 'index.html')));

// ── Boot ───────────────────────────────────────────────────
console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
console.log('  OCI Pricing Agent v2.1 — OCI GenAI Edition');
console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
const _cfg = loadOciConfig();
console.log(`  OCI GenAI : ${_cfg.ok ? `✓ configured (${_cfg.region})` : '✗ not configured — set OCI_* vars in .env'}`);
app.listen(PORT, '0.0.0.0', () => console.log(`\n🚀  http://localhost:${PORT}\n`));
fetchAll();
