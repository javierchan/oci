'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { loadAssistantWithStubs, buildIndex } = require('./assistant-test-helpers');

test('catalog listing returns FastConnect SKUs without asking for region', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs(() => ({
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: 'What FastConnect options are available in the catalog? List all SKUs with hourly prices.',
    assumptions: [],
    serviceFamily: 'network_fastconnect',
    serviceName: '',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: 'Quote OCI FastConnect',
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'What FastConnect options are available in the catalog? List all SKUs with hourly prices.',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.match(reply.message, /B88325/);
  assert.match(reply.message, /B88326/);
  assert.match(reply.message, /B93126/);
  assert.doesNotMatch(reply.message, /what region|which region|tell me the region|please provide the region/i);
});

test('assistant returns greeting guidance before GenAI routing', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs(() => ({
    intent: 'answer',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: 'hola',
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: {},
    confidence: 0.2,
    annualRequested: false,
    normalizedRequest: 'hola',
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'hola',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.match(reply.message, /Puedo ayudarte a cotizar servicios de OCI/i);
});

test('assistant answers FastConnect confidence follow-up before intent analysis', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs(() => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: 'Quote OCI FastConnect 1 Gbps',
    assumptions: [],
    serviceFamily: 'network_fastconnect',
    serviceName: 'OCI FastConnect',
    extractedInputs: { bandwidthGbps: 1 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: 'Quote OCI FastConnect 1 Gbps',
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [{ role: 'user', content: 'Quote OCI FastConnect 1 Gbps' }],
    userText: 'are you sure?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.match(reply.message, /cargo base del puerto/i);
});

test('assistant answers FastConnect region validation follow-up before intent analysis', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs(() => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: 'Quote OCI FastConnect 1 Gbps',
    assumptions: [],
    serviceFamily: 'network_fastconnect',
    serviceName: 'OCI FastConnect',
    extractedInputs: { bandwidthGbps: 1 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: 'Quote OCI FastConnect 1 Gbps',
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [{ role: 'user', content: 'Quote OCI FastConnect 1 Gbps' }],
    userText: 'Queretaro',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.match(reply.message, /mx-queretaro-1/i);
});

test('dns queries quote resolves through generic request-volume pattern', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { requestCount: 5000000 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote OCI DNS 5000000 queries per month',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B88525/);
  assert.match(reply.message, /How OCI measures this:/);
});

test('dns queries quote still resolves correctly when the user appends an explanation request', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { requestCount: 5000000 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote DNS 5000000 queries per month. Explain how OCI measures the main billing dimensions.',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B88525/);
  assert.doesNotMatch(reply.message, /Exadata Cloud@Customer|B110663/);
});

test('email delivery quote resolves through generic request-volume pattern', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { requestCount: 25000 },
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }));

  const reply = await respondToAssistant({
    cfg: {},
    index,
    conversation: [],
    userText: 'Quote Email Delivery 25000 emails per month',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'quote');
  assert.match(reply.message, /B90941/);
});

test('general VM shape options question returns discovery guidance instead of a quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: {},
    confidence: 0.95,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'Sí. En `OCI VM Instances` las familias principales disponibles son:',
      '- `Intel x86`: `VM.Standard3.Flex`, `VM.Optimized3.Flex`, y la línea fija `VM.Standard2.x`.',
      '- `AMD x86`: `VM.Standard.E3.Flex`, `VM.Standard.E4.Flex`, `VM.Standard.E5.Flex`, `VM.Standard.E6.Flex`, y `VM.DenseIO.E4/E5.Flex`.',
      '- `Ampere Arm`: `VM.Standard.A1.Flex`, `VM.Standard.A2.Flex` y `VM.Standard.A4.Flex`.',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Que opciones de Shape tenemos en Virtual Machines?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.match(reply.message, /VM\.Standard3\.Flex/i);
  assert.match(reply.message, /VM\.Standard\.E4\.Flex/i);
  assert.match(reply.message, /VM\.Standard\.A1\.Flex/i);
  assert.doesNotMatch(reply.message, /I prepared a deterministic OCI quotation/i);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.topic, 'vm_shapes');
});

test('vm shape comparison question uses product discovery with structured shape comparison context', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: {},
    confidence: 0.92,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'Para un contexto general:',
      '- `VM.Standard3.Flex` es `Intel x86` general purpose.',
      '- `VM.Standard.E4.Flex` es `AMD x86` general purpose.',
      '- Ambas son `Flex`, así que aceptan `OCPU` y `memoria` definidos por el usuario.',
      '- En ambas familias `x86`, `1 OCPU = 2 vCPUs`.',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Que diferencia hay entre VM.Standard3.Flex y VM.Standard.E4.Flex?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.topic, 'vm_shapes');
  assert.ok(Array.isArray(reply.sessionContext.lastContextPack.shapeComparison));
});

test('pricing model question for WAF uses product discovery with structured pricing dimensions', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'security_waf',
    serviceName: 'Web Application Firewall',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'En `OCI Web Application Firewall` el cobro principal se divide en dos dimensiones:',
      '- cargo fijo por instancia o policy',
      '- cargo variable por volumen de requests',
      'Para cotizar con precisión, normalmente necesitas cantidad de instancias y requests mensuales.',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Como se cobra Web Application Firewall en OCI?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'security_waf');
  assert.ok(Array.isArray(reply.sessionContext.lastContextPack.registryMatchNames));
  assert.match(reply.message, /instancia|policy|requests/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('pricing model question for DNS uses product discovery with structured pricing dimensions', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'network_dns',
    serviceName: 'DNS',
    extractedInputs: {},
    confidence: 0.92,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'En `OCI DNS` el cobro se basa principalmente en el volumen de queries procesadas.',
      '- la dimension de cobro es queries por mes',
      '- para cotizar con precision, normalmente necesitas queries mensuales esperadas',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Como se cobra DNS en OCI?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.ok(reply.sessionContext.lastContextPack.family);
  assert.match(reply.sessionContext.lastContextPack.family.id, /dns/i);
  assert.ok(Array.isArray(reply.sessionContext.lastContextPack.serviceContext?.pricingDimensions || []));
  assert.match(reply.message, /dns|queries/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('pricing model question for API Gateway uses product discovery with structured pricing dimensions', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'apigw',
    serviceName: 'API Gateway',
    extractedInputs: {},
    confidence: 0.92,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'En `OCI API Gateway` el cobro principal se basa en volumen de API calls.',
      '- la unidad de cobro es bloques de llamadas API',
      '- para cotizar con precision, normalmente necesitas llamadas mensuales esperadas',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'How is API Gateway billed in OCI?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.ok(reply.sessionContext.lastContextPack.family);
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'apigw');
  assert.ok(Array.isArray(reply.sessionContext.lastContextPack.serviceContext?.pricingDimensions || []));
  assert.match(reply.message, /api gateway|api calls/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('pricing model question for Health Checks uses structured family context instead of quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'edge_health_checks',
    serviceName: 'Health Checks',
    extractedInputs: {},
    confidence: 0.92,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'En `OCI Health Checks` el cobro se basa principalmente en la cantidad de endpoints monitoreados.',
      '- la unidad de cobro es endpoints por mes',
      '- para cotizar con precisión normalmente necesito el número de endpoints',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'How is Health Checks billed in OCI?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'edge_health_checks');
  assert.match(reply.message, /endpoints?/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('options discovery for Network Firewall uses structured family context instead of quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'network_firewall',
    serviceName: 'Network Firewall',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'En `OCI Network Firewall` normalmente evaluas dos dimensiones principales:',
      '- instancias de firewall',
      '- data processed mensual',
      'Para cotizar, el sizing tipico pide cantidad de firewalls y GB procesados por mes.',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'What options do we have for Network Firewall in OCI?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'network_firewall');
  assert.match(reply.message, /network firewall|instances|data processed|gb/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('licensing discovery question for Base Database uses structured family context instead of quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'database_base_db',
    serviceName: 'Base Database Service',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'En `OCI Base Database Service`, la diferencia principal es el modelo de licenciamiento:',
      '- `BYOL`: reutilizas licencias Oracle elegibles que ya posees.',
      '- `License Included`: el precio del servicio incorpora la licencia correspondiente.',
      'Para una cotización exacta, además necesitas edición, OCPUs o ECPUs, y storage.',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'What is the difference between BYOL and License Included for Base Database Service?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'database_base_db');
  assert.match(reply.message, /BYOL/i);
  assert.match(reply.message, /License Included/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('pricing model question for Object Storage uses product discovery with structured pricing dimensions', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'storage_object',
    serviceName: 'OCI Object Storage',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'En `OCI Object Storage` el cobro principal se basa en capacidad almacenada.',
      '- la dimensión principal es `GB-month` de storage',
      '- para una cotización básica normalmente basta con la capacidad mensual esperada',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Como se cobra Object Storage en OCI?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'storage_object');
  assert.match(reply.message, /GB-month|capacidad/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('pricing model question for File Storage uses product discovery with structured pricing dimensions', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'storage_file',
    serviceName: 'OCI File Storage',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'En `OCI File Storage` normalmente verás dos dimensiones relevantes:',
      '- capacidad provisionada en `GB-month`',
      '- performance units por `GB-month` cuando eliges un nivel de desempeño que las usa',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'How is OCI File Storage billed?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'storage_file');
  assert.match(reply.message, /GB-month|performance units/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('pricing model question for Load Balancer uses structured family context instead of quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'network_load_balancer',
    serviceName: 'OCI Load Balancer',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'En `OCI Load Balancer` normalmente verás dos dimensiones de cobro:',
      '- capacidad base por hora',
      '- bandwidth en `Mbps-hour` para el throughput configurado',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'How is OCI Load Balancer billed?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'network_load_balancer');
  assert.match(reply.message, /bandwidth|Mbps-hour|capacidad base/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('sku composition question for Flexible Load Balancer stays in product discovery even if intent arrives as quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'network_load_balancer',
    serviceName: 'OCI Load Balancer',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'Para una quote de `Flexible Load Balancer` normalmente debes validar dos SKU principales:',
      '- capacidad base del load balancer',
      '- bandwidth configurado en `Mbps-hour`',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: "Cuales son los SKU's requeridos en una quote de Flexible Load Balancer?",
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'network_load_balancer');
  assert.match(reply.message, /bandwidth|capacidad base|SKU/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('options question for FastConnect uses structured family context instead of quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'network_fastconnect',
    serviceName: 'OCI FastConnect',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'En `OCI FastConnect` las opciones comunes se diferencian principalmente por ancho de banda.',
      '- variantes comunes: `1 Gbps`, `10 Gbps` y `100 Gbps`',
      '- la dimensión principal es el puerto por hora asociado al ancho de banda elegido',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'What FastConnect options do we have?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'network_fastconnect');
  assert.match(reply.message, /1 Gbps|10 Gbps|100 Gbps/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('pricing model question for Block Volume uses structured family context instead of quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'storage_block',
    serviceName: 'OCI Block Volume',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'En `OCI Block Volume` normalmente verás dos dimensiones de cobro:',
      '- storage capacity en `GB-month`',
      '- `VPU per GB` cuando eliges niveles de desempeño que usan performance units',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'How is OCI Block Volume billed?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'storage_block');
  assert.match(reply.message, /GB-month|VPU per GB|performance units/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('pricing model question for OCI Functions uses structured family context instead of quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'serverless_functions',
    serviceName: 'OCI Functions',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'En `OCI Functions` el cobro suele combinar varias dimensiones:',
      '- invocations mensuales',
      '- tiempo de ejecución por invocation',
      '- memoria asignada por invocation',
      '- y, si aplica, unidades de provisioned concurrency',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'How is OCI Functions billed?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'serverless_functions');
  assert.match(reply.message, /invocations|execution|memoria|memory|concurrency/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('prerequisite discovery for OCI Data Integration uses structured family context instead of quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'integration_data',
    serviceName: 'OCI Data Integration',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'Para cotizar `OCI Data Integration` normalmente necesito saber:',
      '- si quieres `workspace usage`',
      '- si quieres `data processed`',
      '- la cantidad de workspaces o los GB procesados por hora',
      '- y las horas de ejecución mensuales si aplica',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'What information do I need to quote OCI Data Integration?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'integration_data');
  assert.match(reply.message, /workspace|data processed|hours/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('pricing model question for Data Safe on-prem uses structured family context instead of quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'security_data_safe',
    serviceName: 'OCI Data Safe',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'En `OCI Data Safe` el cobro depende del alcance del servicio:',
      '- `Database Cloud Service` tiene su propia ruta',
      '- `On-Premises Databases` se mide por cantidad de target databases',
      'Para una cotización exacta necesito el tipo de despliegue y el número de databases objetivo.',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'How is Data Safe for On-Premises Databases billed?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'security_data_safe');
  assert.match(reply.message, /target databases|database cloud service|on-premises/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('pricing model question for OCI Monitoring uses structured family context instead of quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'observability_monitoring',
    serviceName: 'OCI Monitoring',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'En `OCI Monitoring` normalmente evalúas dos dimensiones:',
      '- `ingestion` de datapoints',
      '- `retrieval` de datapoints',
      'Para una cotización exacta necesito el volumen esperado de datapoints en la variante que quieras usar.',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'How is OCI Monitoring billed?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'observability_monitoring');
  assert.match(reply.message, /ingestion|retrieval|datapoints/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('pricing model question for Notifications HTTPS Delivery uses structured family context instead of quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'observability_notifications_https',
    serviceName: 'Notifications HTTPS Delivery',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'En `Notifications HTTPS Delivery` el cobro principal se basa en operaciones de entrega.',
      '- la unidad operativa es delivery operations',
      '- para una cotización exacta necesito el volumen mensual esperado',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'How is Notifications HTTPS Delivery billed?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'observability_notifications_https');
  assert.match(reply.message, /delivery operations|https delivery/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('pricing model question for Email Delivery uses structured family context instead of quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'operations_email_delivery',
    serviceName: 'Email Delivery',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'En `Notifications Email Delivery` el cobro principal se basa en volumen de emails enviados.',
      '- la métrica operativa es emails por mes',
      '- para una cotización exacta necesito el volumen mensual esperado',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'How is Email Delivery billed?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'operations_email_delivery');
  assert.match(reply.message, /emails per month|email delivery/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('pricing model question for IAM SMS uses structured family context instead of quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'operations_iam_sms',
    serviceName: 'IAM SMS',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'En `OCI IAM SMS` el cobro se basa en mensajes enviados.',
      '- la métrica operativa es messages',
      '- para una cotización exacta necesito la cantidad de mensajes del periodo',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'How is IAM SMS billed?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'operations_iam_sms');
  assert.match(reply.message, /messages|iam sms/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('pricing model question for Oracle Threat Intelligence Service uses structured family context instead of quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'security_threat_intelligence',
    serviceName: 'Oracle Threat Intelligence Service',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'En `Oracle Threat Intelligence Service` el cobro se basa en volumen de llamadas API.',
      '- la métrica operativa es API calls',
      '- para cotizar necesito el volumen esperado en el periodo',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'How is Oracle Threat Intelligence Service billed?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'security_threat_intelligence');
  assert.match(reply.message, /api calls|threat intelligence/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('pricing model question for Vector Store Retrieval uses structured family context instead of quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'ai_vector_store_retrieval',
    serviceName: 'Vector Store Retrieval',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'En `OCI Generative AI Vector Store Retrieval` el cobro se basa en requests.',
      '- la métrica operativa es requests',
      '- para cotizar necesito el volumen esperado en el periodo',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'How is OCI Generative AI Vector Store Retrieval billed?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'ai_vector_store_retrieval');
  assert.match(reply.message, /requests|vector store/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('pricing model questions for archive, infrequent access, AI variants, vision, and notifications SMS use structured family context instead of quote', async () => {
  const index = buildIndex();
  const cases = [
    ['How is Archive Storage billed?', 'storage_archive', 'Archive Storage', /archive|storage capacity/i, 'En `Archive Storage` el cobro se basa en storage capacity (GB) por mes.'],
    ['How is Infrequent Access Storage billed?', 'storage_infrequent_access', 'Infrequent Access Storage', /infrequent access|retrieval/i, 'En `Infrequent Access Storage` el cobro se basa en storage capacity (GB) y retrieval cuando aplica.'],
    ['How is OCI Generative AI Small Cohere billed?', 'ai_small_cohere', 'OCI Generative AI Small Cohere', /small cohere|transactions/i, 'En `OCI Generative AI Small Cohere` el cobro se basa en transactions.'],
    ['How is OCI Generative AI Embed Cohere billed?', 'ai_embed_cohere', 'OCI Generative AI Embed Cohere', /embed cohere|transactions/i, 'En `OCI Generative AI Embed Cohere` el cobro se basa en transactions.'],
    ['How is OCI Generative AI Large Meta billed?', 'ai_large_meta', 'OCI Generative AI Large Meta', /large meta|transactions/i, 'En `OCI Generative AI Large Meta` el cobro se basa en transactions.'],
    ['How is OCI Vision Image Analysis billed?', 'ai_vision_image_analysis', 'OCI Vision Image Analysis', /image analysis|transactions/i, 'En `OCI Vision Image Analysis` el cobro se basa en transactions.'],
    ['How is OCI Vision OCR billed?', 'ai_vision_ocr', 'OCI Vision OCR', /vision ocr|transactions/i, 'En `OCI Vision OCR` el cobro se basa en transactions.'],
    ['How is OCI Vision Stream Video Analysis billed?', 'ai_vision_stream_video_analysis', 'OCI Vision Stream Video Analysis', /stream video analysis|processed video/i, 'En `OCI Vision Stream Video Analysis` el cobro se basa en processed video minutes.'],
    ['How is OCI Notifications SMS billed?', 'operations_notifications_sms', 'OCI Notifications SMS', /notifications sms|messages/i, 'En `OCI Notifications SMS` el cobro se basa en messages.'],
  ];

  for (const [userText, serviceFamily, serviceName, expected, genaiText] of cases) {
    const { respondToAssistant } = loadAssistantWithStubs((text) => ({
      route: 'product_discovery',
      intent: 'discover',
      shouldQuote: false,
      needsClarification: false,
      clarificationQuestion: '',
      reformulatedRequest: text,
      assumptions: [],
      serviceFamily,
      serviceName,
      extractedInputs: {},
      confidence: 0.9,
      annualRequested: false,
      normalizedRequest: text,
    }), { genaiText });

    const reply = await respondToAssistant({
      cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
      index,
      conversation: [],
      userText,
    });

    assert.equal(reply.ok, true);
    assert.equal(reply.mode, 'answer');
    assert.equal(reply.intent.shouldQuote, false);
    assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
    assert.equal(reply.sessionContext.lastContextPack.family.id, serviceFamily);
    assert.match(reply.message, expected);
    assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
  }
});

test('pricing model question for Vision Custom Training uses structured family context instead of quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'ai_vision_custom_training',
    serviceName: 'Vision Custom Training',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'En `Vision Custom Training` el cobro se basa en training hours.',
      '- la métrica operativa es training hours',
      '- para cotizar necesito el número de horas de entrenamiento',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'How is Vision Custom Training billed in OCI?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'ai_vision_custom_training');
  assert.match(reply.message, /training hours|vision/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('pricing model question for Fleet Application Management uses structured family context instead of quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'ops_fleet_application_management',
    serviceName: 'Fleet Application Management',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'En `OCI Fleet Application Management` el cobro se basa en managed resources.',
      '- la métrica operativa es managed resources por mes',
      '- para cotizar necesito la cantidad de recursos administrados',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'How is OCI Fleet Application Management billed?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'ops_fleet_application_management');
  assert.match(reply.message, /managed resources|fleet/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('pricing model questions for storage, AI variants, vision, and notifications use structured family context instead of quote', async () => {
  const index = buildIndex();
  const cases = [
    {
      userText: 'How is Archive Storage billed?',
      serviceFamily: 'storage_archive',
      serviceName: 'Archive Storage',
      expected: /archive|storage capacity/i,
      genaiText: 'En `Archive Storage` el cobro se basa en storage capacity (GB) por mes.',
    },
    {
      userText: 'How is Infrequent Access Storage billed?',
      serviceFamily: 'storage_infrequent_access',
      serviceName: 'Infrequent Access Storage',
      expected: /infrequent access|storage capacity/i,
      genaiText: 'En `Infrequent Access Storage` el cobro se basa en storage capacity (GB) y retrieval cuando aplica.',
    },
    {
      userText: 'How is OCI Generative AI Small Cohere billed?',
      serviceFamily: 'ai_small_cohere',
      serviceName: 'OCI Generative AI Small Cohere',
      expected: /small cohere|transactions/i,
      genaiText: 'En `OCI Generative AI Small Cohere` el cobro se basa en transactions.',
    },
    {
      userText: 'How is OCI Generative AI Embed Cohere billed?',
      serviceFamily: 'ai_embed_cohere',
      serviceName: 'OCI Generative AI Embed Cohere',
      expected: /embed cohere|transactions/i,
      genaiText: 'En `OCI Generative AI Embed Cohere` el cobro se basa en transactions.',
    },
    {
      userText: 'How is OCI Generative AI Large Meta billed?',
      serviceFamily: 'ai_large_meta',
      serviceName: 'OCI Generative AI Large Meta',
      expected: /large meta|transactions/i,
      genaiText: 'En `OCI Generative AI Large Meta` el cobro se basa en transactions.',
    },
    {
      userText: 'How is OCI Vision Image Analysis billed?',
      serviceFamily: 'ai_vision_image_analysis',
      serviceName: 'OCI Vision Image Analysis',
      expected: /image analysis|transactions/i,
      genaiText: 'En `OCI Vision Image Analysis` el cobro se basa en transactions.',
    },
    {
      userText: 'How is OCI Vision OCR billed?',
      serviceFamily: 'ai_vision_ocr',
      serviceName: 'OCI Vision OCR',
      expected: /vision ocr|transactions/i,
      genaiText: 'En `OCI Vision OCR` el cobro se basa en transactions.',
    },
    {
      userText: 'How is OCI Vision Stream Video Analysis billed?',
      serviceFamily: 'ai_vision_stream_video_analysis',
      serviceName: 'OCI Vision Stream Video Analysis',
      expected: /stream video analysis|processed video/i,
      genaiText: 'En `OCI Vision Stream Video Analysis` el cobro se basa en processed video minutes.',
    },
    {
      userText: 'How is OCI Notifications SMS billed?',
      serviceFamily: 'operations_notifications_sms',
      serviceName: 'OCI Notifications SMS',
      expected: /notifications sms|messages/i,
      genaiText: 'En `OCI Notifications SMS` el cobro se basa en messages.',
    },
  ];

  for (const item of cases) {
    const { respondToAssistant } = loadAssistantWithStubs((text) => ({
      route: 'product_discovery',
      intent: 'discover',
      shouldQuote: false,
      needsClarification: false,
      clarificationQuestion: '',
      reformulatedRequest: text,
      assumptions: [],
      serviceFamily: item.serviceFamily,
      serviceName: item.serviceName,
      extractedInputs: {},
      confidence: 0.9,
      annualRequested: false,
      normalizedRequest: text,
    }), {
      genaiText: item.genaiText,
    });

    const reply = await respondToAssistant({
      cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
      index,
      conversation: [],
      userText: item.userText,
    });

    assert.equal(reply.ok, true);
    assert.equal(reply.mode, 'answer');
    assert.equal(reply.intent.shouldQuote, false);
    assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
    assert.equal(reply.sessionContext.lastContextPack.family.id, item.serviceFamily);
    assert.match(reply.message, item.expected);
    assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
  }
});

test('pricing model question for OCI AI Language uses structured family context instead of quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'ai_language',
    serviceName: 'OCI AI Language',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'En `OCI AI Language` el cobro se basa en transactions.',
      '- la métrica operativa es transactions',
      '- para una cotización exacta necesito el volumen transaccional esperado',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'How is OCI AI Language billed?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'ai_language');
  assert.match(reply.message, /transactions|ai language/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('prerequisite discovery for Oracle Integration Cloud Standard uses structured family context instead of quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'integration_oic_standard',
    serviceName: 'Oracle Integration Cloud Standard',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'Para cotizar `Oracle Integration Cloud Standard` normalmente necesito:',
      '- el modelo de licenciamiento: `BYOL` o `License Included`',
      '- la cantidad de instancias',
      '- y, si aplica en tu caso, cualquier aclaración de moneda o periodo',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'What information do I need to quote Oracle Integration Cloud Standard?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'integration_oic_standard');
  assert.match(reply.message, /BYOL/i);
  assert.match(reply.message, /License Included/i);
  assert.match(reply.message, /instancias|instances/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('pricing model question for Oracle Analytics Cloud Professional uses structured family context instead of quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'analytics_oac_professional',
    serviceName: 'Oracle Analytics Cloud Professional',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'En `Oracle Analytics Cloud Professional` el modelo depende de cómo lo cotices:',
      '- por `users` cuando eliges named users',
      '- por `OCPU-hour` cuando lo cotizas por capacidad de cómputo',
      'Si lo haces por OCPUs, también importa el modo de licenciamiento.',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'How is Oracle Analytics Cloud Professional billed?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'analytics_oac_professional');
  assert.match(reply.message, /users/i);
  assert.match(reply.message, /OCPU/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('pricing model question for Oracle Analytics Cloud Enterprise uses structured family context instead of quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'analytics_oac_enterprise',
    serviceName: 'Oracle Analytics Cloud Enterprise',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'En `Oracle Analytics Cloud Enterprise` el modelo depende de cómo lo cotices:',
      '- por `users` cuando eliges named users',
      '- por `OCPU-hour` cuando lo cotizas por capacidad',
      '- y para OCPUs sí importa el modo `BYOL` o `License Included`',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'How is Oracle Analytics Cloud Enterprise billed?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'analytics_oac_enterprise');
  assert.match(reply.message, /users/i);
  assert.match(reply.message, /OCPU/i);
  assert.match(reply.message, /BYOL|License Included/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('prerequisite discovery for Base Database Service uses structured family context instead of quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'database_base_db',
    serviceName: 'Base Database Service',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'Para cotizar `Base Database Service` normalmente necesito:',
      '- la edición, por ejemplo `Enterprise` o `Standard`',
      '- si será `BYOL` o `License Included`',
      '- la capacidad de cómputo, en `OCPU` o `ECPU` según el caso',
      '- y el storage en GB',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'What information do I need to quote Base Database Service?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'database_base_db');
  assert.match(reply.message, /Enterprise|Standard/i);
  assert.match(reply.message, /BYOL|License Included/i);
  assert.match(reply.message, /OCPU|ECPU/i);
  assert.match(reply.message, /storage/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('options discovery for Exadata Dedicated Infrastructure uses structured family context instead of quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'database_exadata_dedicated',
    serviceName: 'Exadata Dedicated Infrastructure Database',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'Para `Exadata Dedicated Infrastructure Database`, las opciones principales incluyen:',
      '- `BYOL` o `License Included`',
      '- capacidad en `OCPU` o `ECPU`',
      '- y formas de infraestructura como `Base System`',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Que opciones tenemos para Exadata Dedicated Infrastructure?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'database_exadata_dedicated');
  assert.ok(reply.sessionContext.lastContextPack.family.options.infrastructureShapes.includes('Base System'));
  assert.match(reply.message, /BYOL|License Included/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('required-input question for Health Checks stays in product discovery even when intent arrives as quote_request', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'edge_health_checks',
    serviceName: 'Health Checks',
    extractedInputs: {},
    confidence: 0.78,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'network', useDeterministicEngine: true },
  }), {
    genaiText: [
      'Para cotizar `OCI Health Checks` normalmente necesito:',
      '- cantidad de `endpoints`',
      '- confirmar si buscas guidance o una cotización directa',
      'El cobro principal se basa en endpoints monitoreados.',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'What inputs do I need before quoting Health Checks in OCI?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.intent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'edge_health_checks');
  assert.match(reply.message, /Health Checks|endpoints/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('required-input question for Base Database stays in product discovery even when intent arrives as quote_request', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'database_base_db',
    serviceName: 'Base Database Service',
    extractedInputs: {},
    confidence: 0.79,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'database', useDeterministicEngine: true },
  }), {
    genaiText: [
      'Para cotizar `Base Database Service` normalmente necesito:',
      '- edición, por ejemplo `Enterprise` o `Standard`',
      '- `BYOL` o `License Included`',
      '- capacidad en `OCPU` o `ECPU`',
      '- `storage` en GB',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'What inputs do I need before quoting Base Database Service?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.intent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'database_base_db');
  assert.match(reply.message, /Enterprise|Standard/i);
  assert.match(reply.message, /BYOL|License Included/i);
  assert.match(reply.message, /OCPU|ECPU/i);
  assert.match(reply.message, /storage/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('active quote conceptual compute composition question answers instead of mutating the quote', async () => {
  const index = buildIndex();
  const activeQuoteSource = 'Quote VM.Standard.E4.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs';
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_followup',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'compute_flex',
    serviceName: 'Virtual Machine Flex',
    extractedInputs: { ocpus: 4, memoryGb: 16, storageGb: 200, vpuPerGb: 20 },
    confidence: 0.74,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'modify_quote', targetType: 'quote', domain: 'compute', useDeterministicEngine: true },
  }), {
    genaiText: [
      'For a `Virtual Machine Flex` quote, the main components are usually:',
      '- `OCPUs` for compute',
      '- `memory` in GB when the shape is flexible',
      '- optional `Block Storage` and its `VPU` performance level when attached',
      'So no, it is not usually just OCPU unless you intentionally exclude storage and memory from the request.',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Only OCPU, no disk, no memory?',
    sessionContext: {
      lastQuote: {
        source: activeQuoteSource,
        label: 'Virtual Machine Flex',
        serviceFamily: 'compute_flex',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.intent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'compute_flex');
  assert.equal(reply.sessionContext.lastQuote.source, activeQuoteSource);
  assert.match(reply.message, /OCPU|memory|Block Storage|VPU/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('active quote SKU requirement question answers instead of mutating the quote', async () => {
  const index = buildIndex();
  const activeQuoteSource = 'Quote VM.Standard.E4.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage and 20 VPUs';
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_followup',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'compute_flex',
    serviceName: 'Virtual Machine Flex',
    extractedInputs: { ocpus: 4, memoryGb: 16, storageGb: 200, vpuPerGb: 20 },
    confidence: 0.76,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'modify_quote', targetType: 'quote', domain: 'compute', useDeterministicEngine: true },
  }), {
    genaiText: [
      'To quote a `Virtual Machine Flex` stack you normally need the compute and attached component SKUs separated by billing dimension:',
      '- compute `OCPU` SKU',
      '- memory `GB-hour` SKU for Flex memory',
      '- optional `Block Storage` capacity SKU',
      '- optional `VPU` performance SKU',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Which SKUs are required to quote a Virtual Machine instance and its components?',
    sessionContext: {
      lastQuote: {
        source: activeQuoteSource,
        label: 'Virtual Machine Flex',
        serviceFamily: 'compute_flex',
      },
    },
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.intent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'compute_flex');
  assert.equal(reply.sessionContext.lastQuote.source, activeQuoteSource);
  assert.match(reply.message, /SKU|OCPU|memory|Block Storage|VPU/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('billing question for Health Checks with explicit endpoint count stays in discovery instead of being top-service quoted', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { quantity: 12 },
    confidence: 0.77,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'network', useDeterministicEngine: true },
  }), {
    genaiText: [
      'For `OCI Health Checks`, the main billing dimension is the number of monitored `endpoints` per month.',
      '- with `12 endpoints`, the quantity informs the explanation',
      '- but this is still a pricing-model answer, not a deterministic quote request by itself',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'How is OCI Health Checks billed for 12 endpoints?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.intent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'edge_health_checks');
  assert.match(reply.message, /Health Checks|endpoints/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('pricing-dimensions explanation for FastConnect with explicit bandwidth stays in discovery instead of being top-service quoted', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'quote_request',
    intent: 'quote',
    shouldQuote: true,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: { bandwidthGbps: 10 },
    confidence: 0.78,
    annualRequested: false,
    normalizedRequest: text,
    quotePlan: { action: 'quote', targetType: 'service', domain: 'network', useDeterministicEngine: true },
  }), {
    genaiText: [
      'For `OCI FastConnect`, the main billing unit is the selected port bandwidth per hour.',
      '- `10 Gbps` is one of the standard bandwidth options',
      '- this prompt is asking for pricing dimensions, not for a deterministic quote output',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Explain OCI FastConnect pricing dimensions for 10 Gbps.',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.intent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'network_fastconnect');
  assert.match(reply.message, /FastConnect|10 Gbps|bandwidth/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('prerequisite discovery for Oracle Integration Cloud Enterprise uses structured family context instead of quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'integration_oic_enterprise',
    serviceName: 'Oracle Integration Cloud Enterprise',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'Para cotizar `Oracle Integration Cloud Enterprise` normalmente necesito:',
      '- el modelo de licenciamiento: `BYOL` o `License Included`',
      '- la cantidad de instancias',
      '- y cualquier aclaración adicional de moneda o periodo si quieres una presentación distinta del quote estándar',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'What information do I need to quote Oracle Integration Cloud Enterprise?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'integration_oic_enterprise');
  assert.match(reply.message, /BYOL/i);
  assert.match(reply.message, /License Included/i);
  assert.match(reply.message, /instances|instancias/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('generic OIC SKU composition question uses structured discovery instead of a deterministic quote', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: 'integration_oic',
    serviceName: 'Oracle Integration Cloud',
    extractedInputs: {},
    confidence: 0.9,
    annualRequested: false,
    normalizedRequest: text,
  }), {
    genaiText: [
      'Para una quote de `Oracle Integration Cloud` primero debes definir la edición:',
      '- `Standard` o `Enterprise`',
      '- luego el modelo `BYOL` o `License Included`',
      '- y finalmente la cantidad de instancias',
    ].join('\n'),
  });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: "Cuales son los SKU's requeridos en una quote de OIC?",
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.equal(reply.sessionContext.lastIntent.route, 'product_discovery');
  assert.equal(reply.sessionContext.lastContextPack.family.id, 'integration_oic');
  assert.match(reply.message, /Standard/i);
  assert.match(reply.message, /Enterprise/i);
  assert.match(reply.message, /BYOL|License Included/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});

test('general discovery request returns service unavailable instead of inventing a quote when genai fails', async () => {
  const index = buildIndex();
  const { respondToAssistant } = loadAssistantWithStubs((text) => ({
    route: 'product_discovery',
    intent: 'discover',
    shouldQuote: false,
    needsClarification: false,
    clarificationQuestion: '',
    reformulatedRequest: text,
    assumptions: [],
    serviceFamily: '',
    serviceName: '',
    extractedInputs: {},
    confidence: 0.6,
    annualRequested: false,
    normalizedRequest: text,
  }), { throwGenAI: true });

  const reply = await respondToAssistant({
    cfg: { modelId: 'stub-model', compartment: 'stub-compartment' },
    index,
    conversation: [],
    userText: 'Que opciones de Shape tenemos en Virtual Machines?',
  });

  assert.equal(reply.ok, true);
  assert.equal(reply.mode, 'answer');
  assert.equal(reply.intent.shouldQuote, false);
  assert.match(reply.message, /not available/i);
  assert.doesNotMatch(reply.message, /deterministic OCI quotation/i);
});
