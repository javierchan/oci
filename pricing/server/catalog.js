'use strict';

const { loadWorkbookRules, searchWorkbookServices } = require('./workbook-rules');
const { buildServiceRegistry, searchServiceRegistry, serviceHasRequiredInputs } = require('./service-registry');

const MODIFIERS = {
  capacityReservation: new Set('B88513,B88515,B90398,B88517,B89734,B88518,B92740,B88514,B88516,B92306,B92307,B93113,B93114,B97384,B97385,B93297,B93298,B93311,B93312,B94176,B94177'.split(',')),
  preemptible: new Set('B88518,B92740,B88514,B88516,B92306,B92307,B93113,B93114,B93297,B93298,B93311,B93312,B94176,B94177'.split(',')),
  burstable: new Set('B94176,B92306,B93113,B97384,B88318'.split(',')),
};

function normalizeCatalog(rawData) {
  const productsRaw = rawData?.['products.json'];
  const metricsRaw = rawData?.['metrics.json'];
  const presetsRaw = rawData?.['productpresets.json'];

  const productItems = Array.isArray(productsRaw?.items) ? productsRaw.items : (Array.isArray(productsRaw) ? productsRaw : []);
  const metricItems = Array.isArray(metricsRaw?.items) ? metricsRaw.items : (Array.isArray(metricsRaw) ? metricsRaw : []);
  const presetItems = Array.isArray(presetsRaw?.items) ? presetsRaw.items : (Array.isArray(presetsRaw) ? presetsRaw : []);

  const metricsById = new Map();
  for (const metric of metricItems) {
    metricsById.set(String(metric.id), metric);
  }

  const products = [];
  const productsByPartNumber = new Map();

  for (const product of productItems) {
    const metric = metricsById.get(String(product.metricId));
    const localizations = Array.isArray(product.currencyCodeLocalizations) ? product.currencyCodeLocalizations : [];
    const pricingByCurrency = {};
    const tiersByCurrency = {};

    for (const localization of localizations) {
      const currencyCode = localization.currencyCode;
      const prices = Array.isArray(localization.prices) ? localization.prices : [];
      pricingByCurrency[currencyCode] = prices;
      tiersByCurrency[currencyCode] = prices
        .filter((price) => price.model === 'PAY_AS_YOU_GO')
        .map((price) => ({
          model: price.model,
          value: Number(price.value),
          rangeMin: Number.isFinite(Number(price.rangeMin)) ? Number(price.rangeMin) : null,
          rangeMax: Number.isFinite(Number(price.rangeMax)) ? Number(price.rangeMax) : null,
          rangeUnit: price.rangeUnit || null,
        }))
        .sort((a, b) => (a.rangeMin ?? 0) - (b.rangeMin ?? 0));
    }

    const normalized = {
      partNumber: product.partNumber,
      displayName: product.displayName,
      fullDisplayName: product.displayName && product.displayName.includes(product.partNumber)
        ? product.displayName
        : `${product.partNumber} - ${product.displayName}`,
      priceType: product.pricetype || '',
      serviceCategoryDisplayName: product.serviceCategoryDisplayName || '',
      metricId: product.metricId != null ? String(product.metricId) : '',
      metricDisplayName: metric?.displayName || '',
      metricUnitDisplayName: metric?.unitDisplayName || '',
      pricingByCurrency,
      tiersByCurrency,
    };

    products.push(normalized);
    if (!productsByPartNumber.has(normalized.partNumber)) productsByPartNumber.set(normalized.partNumber, []);
    productsByPartNumber.get(normalized.partNumber).push(normalized);
  }

  const presets = presetItems.map((item) => ({
    displayName: item.displayName || '',
    categories: Array.isArray(item.categories) ? item.categories.map((category) => category.displayName || '').filter(Boolean) : [],
    presetItems: Array.isArray(item.presetItems) ? item.presetItems.map((presetItem) => ({
      partNumber: presetItem?.product?.partNumber || '',
    })).filter((presetItem) => presetItem.partNumber) : [],
  }));

  const workbookRules = loadWorkbookRules();
  const baseIndex = {
    products,
    productsByPartNumber,
    metricsById,
    presets,
    modifierSets: MODIFIERS,
  };
  baseIndex.workbookRules = workbookRules;
  baseIndex.serviceRegistry = buildServiceRegistry(baseIndex);
  return baseIndex;
}

function tokenize(value) {
  return String(value || '')
    .toLowerCase()
    .replace(/[^a-z0-9.+#-]+/g, ' ')
    .split(/\s+/)
    .filter(Boolean);
}

const PRODUCT_SEARCH_STOPWORDS = new Set([
  'oci',
  'oracle',
  'cloud',
  'infrastructure',
  'service',
  'services',
  'quote',
  'pricing',
  'price',
]);

function searchProducts(index, query, limit = 12) {
  const q = String(query || '').trim();
  if (!q) return [];
  const qUpper = q.toUpperCase();
  const tokens = tokenize(q).filter((token) => !PRODUCT_SEARCH_STOPWORDS.has(token) && !/^\d+(?:\.\d+)?$/.test(token));
  const scored = [];

  for (const product of index.products) {
    let score = 0;
    const haystack = `${product.fullDisplayName} ${product.serviceCategoryDisplayName} ${product.metricDisplayName}`.toLowerCase();
    if (product.partNumber === qUpper) score += 200;
    else if (product.partNumber.includes(qUpper)) score += 120;
    if (haystack.includes(q.toLowerCase())) score += 80;
    for (const token of tokens) {
      if (product.partNumber.toLowerCase() === token) score += 60;
      else if (haystack.includes(token)) score += 15;
    }
    if (score > 0) scored.push({ score, product });
  }

  scored.sort((a, b) => b.score - a.score || a.product.fullDisplayName.localeCompare(b.product.fullDisplayName));
  return scored.slice(0, limit).map((item) => item.product);
}

function searchPresets(index, query, limit = 8) {
  const q = String(query || '').trim().toLowerCase();
  if (!q) return [];
  const tokens = tokenize(q);
  const scored = [];

  for (const preset of index.presets) {
    let score = 0;
    const haystack = `${preset.displayName} ${preset.categories.join(' ')}`.toLowerCase();
    if (haystack.includes(q)) score += 80;
    for (const token of tokens) {
      if (haystack.includes(token)) score += 10;
    }
    if (score > 0) scored.push({ score, preset });
  }

  scored.sort((a, b) => b.score - a.score || a.preset.displayName.localeCompare(b.preset.displayName));
  return scored.slice(0, limit).map((item) => item.preset);
}

function getPaygTier(product, quantity, currencyCode = 'USD') {
  const tiers = product?.tiersByCurrency?.[currencyCode] || [];
  const usageQty = Number.isFinite(Number(quantity)) ? Number(quantity) : 1;
  if (!tiers.length) return null;

  let tier = tiers.find((entry) => {
    const min = entry.rangeMin ?? 0;
    const max = entry.rangeMax ?? Number.MAX_SAFE_INTEGER;
    return usageQty >= min && usageQty <= max;
  });

  if (!tier) {
    tier = tiers.find((entry) => entry.rangeMin == null && entry.rangeMax == null) || tiers[0];
  }
  return tier || null;
}

function calculatePaygCharge(product, quantity, currencyCode = 'USD') {
  const tiers = product?.tiersByCurrency?.[currencyCode] || [];
  const usageQty = Number.isFinite(Number(quantity)) ? Number(quantity) : 1;
  if (!tiers.length) {
    return {
      ok: false,
      totalCharge: null,
      effectiveUnitPrice: null,
      billedQuantity: usageQty,
      tier: null,
    };
  }

  const normalizedTiers = tiers.map((entry) => ({
    ...entry,
    min: entry.rangeMin ?? 0,
    max: entry.rangeMax ?? Number.MAX_SAFE_INTEGER,
  })).sort((a, b) => a.min - b.min);

  let totalCharge = 0;
  let billedQuantity = 0;
  let matchedTier = null;

  for (const tier of normalizedTiers) {
    if (usageQty <= tier.min) continue;
    const upper = Math.min(usageQty, tier.max);
    const tierQty = Math.max(0, upper - tier.min);
    if (!tierQty) continue;
    totalCharge += tierQty * Number(tier.value || 0);
    billedQuantity += tierQty;
    if (usageQty >= tier.min && usageQty <= tier.max) matchedTier = tier;
  }

  if (!matchedTier) {
    matchedTier = normalizedTiers.find((entry) => entry.min <= usageQty && usageQty <= entry.max) || normalizedTiers[normalizedTiers.length - 1];
  }

  return {
    ok: true,
    totalCharge,
    effectiveUnitPrice: usageQty > 0 ? totalCharge / usageQty : 0,
    billedQuantity,
    tier: matchedTier || null,
  };
}

module.exports = {
  MODIFIERS,
  normalizeCatalog,
  searchProducts,
  searchPresets,
  searchWorkbookServices,
  searchServiceRegistry,
  serviceHasRequiredInputs,
  getPaygTier,
  calculatePaygCharge,
};
