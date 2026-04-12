'use strict';

const { quoteFromPrompt } = require('./quotation-engine');

const CAPACITY_RESERVATION_CLARIFICATION = {
  ok: true,
  mode: 'clarification',
  message: 'For the Flex shape comparison, what capacity reservation utilization should I use: for example `1.0`, `0.7`, or `0.5`?',
  intent: {
    intent: 'quote',
    shouldQuote: true,
    needsClarification: true,
    clarificationQuestion: 'What capacity reservation utilization should I use for the comparison?',
  },
};

const BURSTABLE_BASELINE_CLARIFICATION = {
  ok: true,
  mode: 'clarification',
  message: 'For the Flex shape comparison, what burstable baseline should I use: for example `0.5`, `0.25`, or `0.125`?',
  intent: {
    intent: 'quote',
    shouldQuote: true,
    needsClarification: true,
    clarificationQuestion: 'What burstable baseline should I use for the comparison?',
  },
};

const ON_DEMAND_SIDE_CLARIFICATION = {
  ok: true,
  mode: 'clarification',
  message: 'For the non-capacity-reservation side of the comparison, should I use `On demand` pricing?',
  intent: {
    intent: 'quote',
    shouldQuote: true,
    needsClarification: true,
    clarificationQuestion: 'Should I use On demand pricing for the non-capacity-reservation side?',
  },
};

const UNSUPPORTED_NON_ON_DEMAND_CLARIFICATION = {
  ok: true,
  mode: 'clarification',
  message: 'Reserved pricing for the non-capacity-reservation side is not modeled yet in this comparison flow. If you want, reply with `On demand` and I will generate the deterministic comparison.',
  intent: {
    intent: 'quote',
    shouldQuote: true,
    needsClarification: true,
    clarificationQuestion: 'Reply with On demand to continue the Flex comparison.',
  },
};

function buildFlexComparisonClarificationPayload({
  modifierKind = '',
  utilization = null,
  burstableBaseline = null,
  withoutCrMode = '',
  requireWithoutCrMode = false,
} = {}) {
  if (modifierKind === 'capacity-reservation' && utilization === null) {
    return { ...CAPACITY_RESERVATION_CLARIFICATION };
  }
  if (modifierKind === 'burstable' && burstableBaseline === null) {
    return { ...BURSTABLE_BASELINE_CLARIFICATION };
  }
  if (requireWithoutCrMode && modifierKind === 'capacity-reservation' && !withoutCrMode) {
    return { ...ON_DEMAND_SIDE_CLARIFICATION };
  }
  if (requireWithoutCrMode && modifierKind === 'capacity-reservation' && withoutCrMode !== 'on-demand') {
    return { ...UNSUPPORTED_NON_ON_DEMAND_CLARIFICATION };
  }
  return null;
}

function money(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) return '$-';
  return `$${Number(num.toFixed(4))}`;
}

function resolveEarlyFlexComparisonClarification({
  effectiveUserText = '',
  isFlexComparisonRequest,
  detectFlexComparisonModifier,
  parseCapacityReservationUtilization,
  parseBurstableBaseline,
} = {}) {
  if (typeof isFlexComparisonRequest !== 'function' || !isFlexComparisonRequest(effectiveUserText)) {
    return null;
  }
  const modifierKind = typeof detectFlexComparisonModifier === 'function'
    ? detectFlexComparisonModifier(effectiveUserText)
    : '';
  return buildFlexComparisonClarificationPayload({
    modifierKind,
    utilization: typeof parseCapacityReservationUtilization === 'function'
      ? parseCapacityReservationUtilization(effectiveUserText)
      : null,
    burstableBaseline: typeof parseBurstableBaseline === 'function'
      ? parseBurstableBaseline(effectiveUserText)
      : null,
  });
}

function buildFlexComparisonQuote(index, context) {
  const rows = [];
  const warnings = [];
  for (const shape of context.shapes) {
    const basePrompt = `Quote ${shape} ${context.ocpus} OCPUs ${context.memoryGb} GB RAM ${context.hours}h`;
    const onDemandQuote = quoteFromPrompt(index, basePrompt);
    let variantPrompt = '';
    if (context.modifierKind === 'capacity-reservation') variantPrompt = `${basePrompt} capacity reservation ${context.utilization}`;
    if (context.modifierKind === 'preemptible') variantPrompt = `${basePrompt} preemptible`;
    if (context.modifierKind === 'burstable') variantPrompt = `${basePrompt} burstable baseline ${context.burstableBaseline}`;
    const modifierQuote = quoteFromPrompt(index, variantPrompt);
    if (!onDemandQuote.ok || !modifierQuote.ok) {
      warnings.push(`Could not build a complete comparison for ${shape}.`);
      continue;
    }
    if (Array.isArray(onDemandQuote.warnings) && onDemandQuote.warnings.length) {
      warnings.push(...onDemandQuote.warnings.map((item) => `${shape.toUpperCase()}: ${item}`));
    }
    if (Array.isArray(modifierQuote.warnings) && modifierQuote.warnings.length) {
      warnings.push(...modifierQuote.warnings.map((item) => `${shape.toUpperCase()}: ${item}`));
    }
    rows.push({
      shape: shape.toUpperCase(),
      onDemandMonthly: Number(onDemandQuote.totals?.monthly || 0),
      variantMonthly: Number(modifierQuote.totals?.monthly || 0),
      deltaMonthly: Number(modifierQuote.totals?.monthly || 0) - Number(onDemandQuote.totals?.monthly || 0),
      onDemandAnnual: Number(onDemandQuote.totals?.annual || 0),
      variantAnnual: Number(modifierQuote.totals?.annual || 0),
    });
  }
  if (!rows.length) {
    return { ok: false, warnings: warnings.length ? warnings : ['No Flex shapes could be compared.'] };
  }
  rows.sort((a, b) => a.onDemandMonthly - b.onDemandMonthly);
  const variantLabel = context.modifierKind === 'capacity-reservation'
    ? 'Capacity Reservation'
    : context.modifierKind === 'preemptible'
      ? 'Preemptible'
      : 'Burstable';
  const markdown = [
    `| Shape | On-demand $/Mo | ${variantLabel} $/Mo | Delta $/Mo | On-demand Annual | ${variantLabel} Annual |`,
    '|---|---:|---:|---:|---:|---:|',
    ...rows.map((row) => `| ${row.shape} | ${money(row.onDemandMonthly)} | ${money(row.variantMonthly)} | ${money(row.deltaMonthly)} | ${money(row.onDemandAnnual)} | ${money(row.variantAnnual)} |`),
  ].join('\n');
  return { ok: true, rows, markdown, warnings: Array.from(new Set(warnings)) };
}

function buildFlexComparisonNarrative(context, comparison) {
  const modifierLabel = context.modifierKind === 'capacity-reservation'
    ? 'Capacity Reservation'
    : context.modifierKind === 'preemptible'
      ? 'Preemptible'
      : 'Burstable';
  const assumptions = [
    `- Compared shapes: ${context.shapes.map((shape) => shape.toUpperCase()).join(', ')}.`,
    `- Size used for each shape: ${context.ocpus} OCPUs, ${context.memoryGb} GB RAM, ${context.hours} hours/month.`,
    `- Base side uses on-demand pricing.`,
  ];
  if (context.modifierKind === 'capacity-reservation') {
    assumptions.push(`- Non-capacity-reservation side uses ${context.withoutCrMode}.`);
    assumptions.push(`- Capacity reservation utilization: ${context.utilization}.`);
  }
  if (context.modifierKind === 'burstable') {
    assumptions.push(`- Burstable baseline: ${context.burstableBaseline}.`);
  }
  if (comparison.warnings?.length) {
    assumptions.push(...comparison.warnings.map((item) => `- ${item}`));
  }
  return [
    `I prepared a deterministic OCI Flex shape comparison for \`${context.shapes.map((shape) => shape.toUpperCase()).join(' vs ')}\`.`,
    `The comparison shows the monthly and annual totals with and without ${modifierLabel} for the same sizing.`,
    `Key assumptions:\n${assumptions.join('\n')}`,
    `### OCI comparison\n\n${comparison.markdown}`,
  ].join('\n\n');
}

function buildFlexComparisonReplyPayload({
  index,
  flexComparison,
  buildFlexComparisonQuote,
  buildFlexComparisonNarrative,
} = {}) {
  if (!flexComparison) return null;

  const clarification = buildFlexComparisonClarificationPayload({
    modifierKind: flexComparison.modifierKind,
    utilization: flexComparison.utilization,
    burstableBaseline: flexComparison.burstableBaseline,
    withoutCrMode: flexComparison.withoutCrMode,
    requireWithoutCrMode: true,
  });
  if (clarification) return clarification;

  const quoteBuilder = typeof buildFlexComparisonQuote === 'function' ? buildFlexComparisonQuote : buildFlexComparisonQuoteDefault;
  const narrativeBuilder = typeof buildFlexComparisonNarrative === 'function' ? buildFlexComparisonNarrative : buildFlexComparisonNarrativeDefault;

  const comparison = quoteBuilder(index, flexComparison);
  if (!comparison?.ok) return null;

  return {
    ok: true,
    mode: 'quote',
    message: narrativeBuilder(flexComparison, comparison),
    quote: {
      ok: true,
      request: {
        source: flexComparison.basePrompt,
        comparison: true,
      },
      comparison,
    },
    intent: {
      intent: 'quote',
      shouldQuote: true,
      needsClarification: false,
      clarificationQuestion: '',
    },
  };
}

const buildFlexComparisonQuoteDefault = buildFlexComparisonQuote;
const buildFlexComparisonNarrativeDefault = buildFlexComparisonNarrative;

module.exports = {
  buildFlexComparisonClarificationPayload,
  resolveEarlyFlexComparisonClarification,
  buildFlexComparisonQuote,
  buildFlexComparisonNarrative,
  buildFlexComparisonReplyPayload,
};
