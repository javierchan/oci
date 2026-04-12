'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const {
  getActiveQuoteFollowUpReplacementRules,
  getFollowUpCapabilityMatrix,
  getCompositeFollowUpRemovalRules,
  normalizeExtractedInputsForFamily,
  supportsFollowUpCapability,
} = require(path.join(ROOT, 'service-families.js'));

test('service family normalization maps generic WAF instanceCount into wafInstances', () => {
  const normalized = normalizeExtractedInputsForFamily('security_waf', {
    instanceCount: 2,
    requestCount: 25000000,
  });

  assert.equal(normalized.wafInstances, 2);
  assert.equal(normalized.requestCount, 25000000);
});

test('service family normalization does not override an explicit wafInstances value', () => {
  const normalized = normalizeExtractedInputsForFamily('security_waf', {
    instanceCount: 2,
    wafInstances: 4,
  });

  assert.equal(normalized.wafInstances, 4);
});

test('service family normalization maps generic data-safe database count into quantity', () => {
  const normalized = normalizeExtractedInputsForFamily('security_data_safe', {
    numberOfDatabases: 3,
  });

  assert.equal(normalized.quantity, 3);
});

test('base database keeps license follow-up support when compute sizing is present', () => {
  assert.equal(
    supportsFollowUpCapability('database_base_db', 'licenseMode', {
      ocpus: 8,
      capacityGb: 2000,
      databaseEdition: 'Enterprise',
    }),
    true,
  );
});

test('oac professional skips license follow-up support for named-user quotes', () => {
  assert.equal(
    supportsFollowUpCapability('analytics_oac_professional', 'licenseMode', {
      users: 25,
    }),
    false,
  );
});

test('oac professional keeps license follow-up support for ocpu quotes', () => {
  assert.equal(
    supportsFollowUpCapability('analytics_oac_professional', 'licenseMode', {
      ocpus: 2,
    }),
    true,
  );
});

test('oac professional keeps license follow-up support for ocpu quotes when users is explicitly null', () => {
  assert.equal(
    supportsFollowUpCapability('analytics_oac_professional', 'licenseMode', {
      ocpus: 2,
      users: null,
    }),
    true,
  );
});

test('oac enterprise skips license follow-up support for named-user quotes', () => {
  assert.equal(
    supportsFollowUpCapability('analytics_oac_enterprise', 'licenseMode', {
      users: 50,
    }),
    false,
  );
});

test('oic and oac sibling families expose composite replacement capability declaratively', () => {
  const families = [
    'integration_oic_standard',
    'integration_oic_enterprise',
    'analytics_oac_professional',
    'analytics_oac_enterprise',
  ];

  for (const familyId of families) {
    assert.equal(supportsFollowUpCapability(familyId, 'compositeReplaceSource'), true);
    assert.equal(supportsFollowUpCapability(familyId, 'compositeReplaceTarget'), true);
  }
});

test('data safe and log analytics expose composite replacement capability declaratively', () => {
  const families = [
    'security_data_safe',
    'observability_log_analytics',
  ];

  for (const familyId of families) {
    assert.equal(supportsFollowUpCapability(familyId, 'compositeReplaceSource'), true);
    assert.equal(supportsFollowUpCapability(familyId, 'compositeReplaceTarget'), true);
  }
});

test('data safe follow-up metadata includes variant and quantity replacement rules', () => {
  const rules = getActiveQuoteFollowUpReplacementRules('security_data_safe');

  assert.equal(rules.length >= 3, true);
  assert.match(String(rules[0].sourcePattern), /database cloud service|on-\?prem/);
  assert.match(String(rules[1].sourcePattern), /target\\s\+databases/);
  assert.match(String(rules[2].sourcePattern), /databases/);
});

test('log analytics follow-up metadata includes variant and capacity replacement rules', () => {
  const rules = getActiveQuoteFollowUpReplacementRules('observability_log_analytics');

  assert.equal(rules.length, 2);
  assert.match(String(rules[0].sourcePattern), /active\|archiv/);
  assert.match(String(rules[1].sourcePattern), /gb/);
});

test('monitoring follow-up metadata includes variant and datapoint replacement rules', () => {
  const rules = getActiveQuoteFollowUpReplacementRules('observability_monitoring');

  assert.equal(rules.length, 2);
  assert.match(String(rules[0].sourcePattern), /monitoring/);
  assert.match(String(rules[0].sourcePattern), /retrieval\|ingestion|ingestion\|retrieval/);
  assert.match(String(rules[1].sourcePattern), /datapoints/);
});

test('composite removal registry includes data safe and log analytics families', () => {
  const removals = getCompositeFollowUpRemovalRules();
  const familyIds = removals.map((entry) => entry.familyId);

  assert.ok(familyIds.includes('security_data_safe'));
  assert.ok(familyIds.includes('observability_log_analytics'));
});

test('follow-up capability matrix summarizes hardened family behavior declaratively', () => {
  const matrix = getFollowUpCapabilityMatrix();

  const oicStandard = matrix.find((entry) => entry.familyId === 'integration_oic_standard');
  const dataSafe = matrix.find((entry) => entry.familyId === 'security_data_safe');
  const logAnalytics = matrix.find((entry) => entry.familyId === 'observability_log_analytics');
  const monitoring = matrix.find((entry) => entry.familyId === 'observability_monitoring');
  const waf = matrix.find((entry) => entry.familyId === 'security_waf');
  const baseDb = matrix.find((entry) => entry.familyId === 'database_base_db');

  assert.ok(oicStandard);
  assert.equal(oicStandard.compositeReplaceSource, true);
  assert.equal(oicStandard.compositeReplaceTarget, true);
  assert.equal(oicStandard.compositeRemove, true);
  assert.equal(oicStandard.hasActiveQuoteRules, true);

  assert.ok(dataSafe);
  assert.equal(dataSafe.compositeRemove, true);
  assert.equal(dataSafe.compositeReplaceSource, true);
  assert.equal(dataSafe.compositeReplaceTarget, true);
  assert.equal(dataSafe.hasActiveQuoteRules, true);
  assert.equal(dataSafe.activeQuoteRuleCount >= 3, true);

  assert.ok(logAnalytics);
  assert.equal(logAnalytics.compositeRemove, true);
  assert.equal(logAnalytics.compositeReplaceSource, true);
  assert.equal(logAnalytics.compositeReplaceTarget, true);
  assert.equal(logAnalytics.hasActiveQuoteRules, true);
  assert.equal(logAnalytics.activeQuoteRuleCount, 2);

  assert.ok(monitoring);
  assert.equal(monitoring.compositeRemove, true);
  assert.equal(monitoring.compositeReplaceSource, true);
  assert.equal(monitoring.compositeReplaceTarget, true);
  assert.equal(monitoring.hasActiveQuoteRules, true);
  assert.equal(monitoring.activeQuoteRuleCount, 2);

  assert.ok(waf);
  assert.equal(waf.canonical, 'OCI Web Application Firewall');
  assert.equal(waf.compositeRemove, true);
  assert.equal(waf.compositeReplaceSource, true);
  assert.equal(waf.compositeReplaceTarget, true);
  assert.equal(waf.hasActiveQuoteRules, true);
  assert.equal(waf.activeQuoteRuleCount >= 1, true);

  assert.ok(baseDb);
  assert.equal(baseDb.licenseMode, true);
  assert.equal(baseDb.hasActiveQuoteRules, true);
});
