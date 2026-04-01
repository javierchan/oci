'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');
const XLSX = require('xlsx');

const ROOT = path.resolve(__dirname, '..');
const {
  workbookToRequests,
  analyzeWorkbookForGuidedQuote,
  buildShapeOptionsForProcessor,
  parseWorkbookPromptSelections,
  hasWorkbookSelection,
} = require(path.join(ROOT, 'excel.js'));
const { buildQuote } = require(path.join(ROOT, 'quotation-engine.js'));
const { normalizeCatalog } = require(path.join(ROOT, 'catalog.js'));

function metric(id, displayName, unitDisplayName = '') {
  return { id, displayName, unitDisplayName };
}

function payg(value, rangeMin, rangeMax) {
  const tier = { model: 'PAY_AS_YOU_GO', value };
  if (rangeMin !== undefined) tier.rangeMin = rangeMin;
  if (rangeMax !== undefined) tier.rangeMax = rangeMax;
  return tier;
}

function product({
  partNumber,
  displayName,
  serviceCategoryDisplayName,
  metricId,
  pricetype = 'HOUR',
  usdPrices = [payg(1)],
}) {
  return {
    partNumber,
    displayName,
    serviceCategoryDisplayName,
    metricId,
    pricetype,
    currencyCodeLocalizations: [
      {
        currencyCode: 'USD',
        prices: usdPrices,
      },
    ],
  };
}

function buildIndex() {
  return normalizeCatalog({
    'metrics.json': {
      items: [
        metric('m-ocpu-hour', 'OCPU Per Hour'),
        metric('m-gb-hour', 'Gigabyte RAM Per Hour'),
        metric('m-capacity-month', 'Gigabyte Storage Capacity Per Month'),
        metric('m-performance-month', 'Performance Units Per Gigabyte Per Month'),
      ],
    },
    'products.json': {
      items: [
        product({
          partNumber: 'B94176',
          displayName: 'Compute - Standard - X9 - OCPU',
          serviceCategoryDisplayName: 'Compute - Virtual Machine',
          metricId: 'm-ocpu-hour',
          usdPrices: [payg(0.04)],
        }),
        product({
          partNumber: 'B94177',
          displayName: 'Compute - Standard - X9 - Memory',
          serviceCategoryDisplayName: 'Compute - Virtual Machine',
          metricId: 'm-gb-hour',
          usdPrices: [payg(0.0015)],
        }),
        product({
          partNumber: 'B93113',
          displayName: 'Compute - Standard - E4 - OCPU',
          serviceCategoryDisplayName: 'Compute - Virtual Machine',
          metricId: 'm-ocpu-hour',
          usdPrices: [payg(0.025)],
        }),
        product({
          partNumber: 'B93114',
          displayName: 'Compute - Standard - E4 - Memory',
          serviceCategoryDisplayName: 'Compute - Virtual Machine',
          metricId: 'm-gb-hour',
          usdPrices: [payg(0.005)],
        }),
        product({
          partNumber: 'B91961',
          displayName: 'Storage - Block Volume - Storage',
          serviceCategoryDisplayName: 'Storage - Block Volumes',
          metricId: 'm-capacity-month',
          pricetype: 'MONTH',
          usdPrices: [payg(0.0255)],
        }),
        product({
          partNumber: 'B91962',
          displayName: 'Storage - Block Volume - Performance Units',
          serviceCategoryDisplayName: 'Storage - Block Volumes',
          metricId: 'm-performance-month',
          pricetype: 'MONTH',
          usdPrices: [payg(0.0017)],
        }),
      ],
    },
    'productpresets.json': { items: [] },
    'xls-extract.json': { items: [] },
  });
}

test('inventory workbook rows are converted into quotable compute plus block storage requests', () => {
  const sheet = XLSX.utils.json_to_sheet([
    {
      HW: 'Servidor',
      'Nombre Equipo': 'bm-demo-01',
      CPU: '2 x Intel(R) Xeon(R) CPU E5-2690 v4 @ 2.60GHz',
      Cores: '14',
      'Memoria Gb': '256',
      'Aprovisionado Gb': '121.2',
      SO: 'Oracle Linux 7',
    },
    {
      HW: 'Total',
      'Nombre Equipo': 'Total',
      CPU: '',
      Cores: '',
      'Memoria Gb': '',
      'Aprovisionado Gb': '',
      SO: '',
    },
  ]);
  const workbook = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(workbook, sheet, 'Bare Metal to OCI');

  const parsed = workbookToRequests(workbook);

  assert.equal(parsed.requests.length, 1);
  assert.match(parsed.requests[0].source, /Quote VM\.Standard3\.Flex 28 OCPUs 256 GB RAM with 121\.2 GB Block Storage/);
  assert.equal(parsed.requests[0].environment, 'bm-demo-01');
  assert.equal(parsed.requests[0].shape.series, 'X9');
  assert.equal(parsed.requests[0].ocpus, 28);
  assert.equal(parsed.requests[0].memoryQuantity, 256);
  assert.equal(parsed.requests[0].capacityGb, 121.2);
  assert.equal(parsed.requests[0].metadata.inventorySource, 'inventory_workbook');
  assert.match(parsed.warnings.join('\n'), /mapped heuristically to OCI VM\.Standard3\.Flex/i);
});

test('inventory workbook-derived request is quotable as flex compute plus block volume', () => {
  const sheet = XLSX.utils.json_to_sheet([
    {
      HW: 'Servidor',
      'Nombre Equipo': 'bm-demo-02',
      CPU: '2 x Intel(R) Xeon(R) CPU E5-2690 v4 @ 2.60GHz',
      Cores: '14',
      'Memoria Gb': '256',
      'Aprovisionado Gb': '121.2',
      SO: 'Windows Server 2008',
    },
  ]);
  const workbook = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(workbook, sheet, 'Bare Metal to OCI');

  const parsed = workbookToRequests(workbook);
  const quote = buildQuote(buildIndex(), parsed.requests[0]);

  assert.equal(parsed.requests.length, 1);
  assert.match(parsed.warnings.join('\n'), /without separate Windows licensing adjustments/i);
  assert.equal(quote.ok, true);
  assert.equal(quote.lineItems.length, 4);
  const partNumbers = quote.lineItems.map((line) => line.partNumber).sort();
  assert.deepEqual(partNumbers, ['B91961', 'B91962', 'B94176', 'B94177']);
});

test('inventory workbook honors workbook-level VPU overrides from the guided flow', () => {
  const sheet = XLSX.utils.json_to_sheet([
    {
      HW: 'Servidor',
      'Nombre Equipo': 'bm-demo-03',
      CPU: '2 x Intel(R) Xeon(R) CPU E5-2690 v4 @ 2.60GHz',
      Cores: '14',
      'Memoria Gb': '256',
      'Aprovisionado Gb': '121.2',
      SO: 'Oracle Linux 7',
    },
  ]);
  const workbook = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(workbook, sheet, 'Bare Metal to OCI');

  const parsed = workbookToRequests(workbook, {
    processorVendor: 'intel',
    shapeName: 'VM.Standard3.Flex',
    vpuPerGb: 30,
  });
  const quote = buildQuote(buildIndex(), parsed.requests[0]);

  assert.equal(parsed.requests.length, 1);
  assert.match(parsed.requests[0].source, /121\.2 GB Block Storage and 30 VPUs/);
  assert.equal(parsed.requests[0].vpuPerGb, 30);
  assert.match(parsed.warnings.join('\n'), /30 VPU/i);
  assert.equal(quote.ok, true);
  const performanceLine = quote.lineItems.find((line) => line.partNumber === 'B91962');
  assert.ok(performanceLine);
  assert.equal(performanceLine.quantity, 3636);
});

test('rvtools workbook rows are converted into quotable OCI requests from vInfo/vCPU/vMemory/vDisk sheets', () => {
  const workbook = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(workbook, XLSX.utils.json_to_sheet([
    {
      VM: 'rv-vm-01',
      Powerstate: 'poweredOn',
      Template: 'False',
      'SRM Placeholder': 'False',
      CPUs: '8',
      Memory: '16,384',
      'Total disk capacity MiB': '204,800',
      'min Required EVC Mode Key': 'intel-cascadelake',
      Cluster: 'cluster-a',
      'OS according to the configuration file': 'Oracle Linux 8 (64-bit)',
      'OS according to the VMware Tools': 'Oracle Linux 8 (64-bit)',
    },
  ]), 'vInfo');
  XLSX.utils.book_append_sheet(workbook, XLSX.utils.json_to_sheet([
    { VM: 'rv-vm-01', CPUs: '8', Sockets: '2', 'Cores p/s': '4' },
  ]), 'vCPU');
  XLSX.utils.book_append_sheet(workbook, XLSX.utils.json_to_sheet([
    { VM: 'rv-vm-01', 'Size MiB': '16,384' },
  ]), 'vMemory');
  XLSX.utils.book_append_sheet(workbook, XLSX.utils.json_to_sheet([
    { VM: 'rv-vm-01', 'Disk': 'Hard disk 1', 'Capacity MiB': '102,400' },
    { VM: 'rv-vm-01', 'Disk': 'Hard disk 2', 'Capacity MiB': '102,400' },
  ]), 'vDisk');

  const parsed = workbookToRequests(workbook);

  assert.equal(parsed.requests.length, 1);
  assert.match(parsed.requests[0].source, /Quote VM\.Standard3\.Flex 4 OCPUs 16 GB RAM with 200 GB Block Storage/);
  assert.equal(parsed.requests[0].environment, 'rv-vm-01');
  assert.equal(parsed.requests[0].shape.series, 'X9');
  assert.equal(parsed.requests[0].metadata.vmwareVcpus, 8);
  assert.match(parsed.warnings.join('\n'), /2 VMware vCPUs to 1 OCI OCPU/i);
});

test('rvtools workbook-derived request is quotable as compute plus block storage', () => {
  const workbook = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(workbook, XLSX.utils.json_to_sheet([
    {
      VM: 'rv-win-01',
      Powerstate: 'poweredOff',
      Template: 'False',
      'SRM Placeholder': 'False',
      CPUs: '4',
      Memory: '8,192',
      'Total disk capacity MiB': '71,680',
      'min Required EVC Mode Key': 'intel-broadwell',
      'OS according to the configuration file': 'Microsoft Windows Server 2019 (64-bit)',
      'OS according to the VMware Tools': 'Microsoft Windows Server 2019 (64-bit)',
    },
  ]), 'vInfo');
  XLSX.utils.book_append_sheet(workbook, XLSX.utils.json_to_sheet([
    { VM: 'rv-win-01', CPUs: '4', Sockets: '2', 'Cores p/s': '2' },
  ]), 'vCPU');
  XLSX.utils.book_append_sheet(workbook, XLSX.utils.json_to_sheet([
    { VM: 'rv-win-01', 'Size MiB': '8,192' },
  ]), 'vMemory');
  XLSX.utils.book_append_sheet(workbook, XLSX.utils.json_to_sheet([
    { VM: 'rv-win-01', 'Disk': 'Hard disk 1', 'Capacity MiB': '71,680' },
  ]), 'vDisk');

  const parsed = workbookToRequests(workbook);
  const quote = buildQuote(buildIndex(), parsed.requests[0]);

  assert.equal(parsed.requests.length, 1);
  assert.match(parsed.warnings.join('\n'), /Windows licensing adjustments/i);
  assert.match(parsed.warnings.join('\n'), /powered-off VMs/i);
  assert.equal(quote.ok, true);
  assert.equal(quote.lineItems.length, 4);
});

test('rvtools workbook honors workbook-level VPU overrides from the guided flow', () => {
  const workbook = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(workbook, XLSX.utils.json_to_sheet([
    {
      VM: 'rv-vm-02',
      Powerstate: 'poweredOn',
      Template: 'False',
      'SRM Placeholder': 'False',
      CPUs: '8',
      Memory: '16,384',
      'Total disk capacity MiB': '102,400',
      'min Required EVC Mode Key': 'intel-cascadelake',
      'OS according to the configuration file': 'Oracle Linux 8 (64-bit)',
      'OS according to the VMware Tools': 'Oracle Linux 8 (64-bit)',
    },
  ]), 'vInfo');
  XLSX.utils.book_append_sheet(workbook, XLSX.utils.json_to_sheet([
    { VM: 'rv-vm-02', CPUs: '8', Sockets: '2', 'Cores p/s': '4' },
  ]), 'vCPU');
  XLSX.utils.book_append_sheet(workbook, XLSX.utils.json_to_sheet([
    { VM: 'rv-vm-02', 'Size MiB': '16,384' },
  ]), 'vMemory');
  XLSX.utils.book_append_sheet(workbook, XLSX.utils.json_to_sheet([
    { VM: 'rv-vm-02', 'Disk': 'Hard disk 1', 'Capacity MiB': '102,400' },
  ]), 'vDisk');

  const parsed = workbookToRequests(workbook, {
    processorVendor: 'intel',
    shapeName: 'VM.Standard3.Flex',
    vpuPerGb: 30,
  });
  const quote = buildQuote(buildIndex(), parsed.requests[0]);

  assert.equal(parsed.requests.length, 1);
  assert.match(parsed.requests[0].source, /100 GB Block Storage and 30 VPUs/);
  assert.equal(parsed.requests[0].vpuPerGb, 30);
  assert.match(parsed.warnings.join('\n'), /30 VPU/i);
  assert.equal(quote.ok, true);
  const performanceLine = quote.lineItems.find((line) => line.partNumber === 'B91962');
  assert.ok(performanceLine);
  assert.equal(performanceLine.quantity, 3000);
});

test('rvtools parser skips VMware service VMs such as vCLS', () => {
  const workbook = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(workbook, XLSX.utils.json_to_sheet([
    {
      VM: 'vCLS-123456',
      Powerstate: 'poweredOn',
      Template: 'False',
      'SRM Placeholder': 'False',
      CPUs: '2',
      Memory: '2,048',
      'Total disk capacity MiB': '16,384',
      Cluster: 'cluster-a',
      'OS according to the configuration file': 'Other Linux (64-bit)',
    },
    {
      VM: 'app-01',
      Powerstate: 'poweredOn',
      Template: 'False',
      'SRM Placeholder': 'False',
      CPUs: '4',
      Memory: '8,192',
      'Total disk capacity MiB': '51,200',
      Cluster: 'cluster-a',
      'min Required EVC Mode Key': 'intel-cascadelake',
      'OS according to the configuration file': 'Oracle Linux 8 (64-bit)',
    },
  ]), 'vInfo');
  XLSX.utils.book_append_sheet(workbook, XLSX.utils.json_to_sheet([
    { VM: 'vCLS-123456', CPUs: '2' },
    { VM: 'app-01', CPUs: '4' },
  ]), 'vCPU');
  XLSX.utils.book_append_sheet(workbook, XLSX.utils.json_to_sheet([
    { VM: 'vCLS-123456', 'Size MiB': '2,048' },
    { VM: 'app-01', 'Size MiB': '8,192' },
  ]), 'vMemory');
  XLSX.utils.book_append_sheet(workbook, XLSX.utils.json_to_sheet([
    { VM: 'vCLS-123456', 'Capacity MiB': '16,384' },
    { VM: 'app-01', 'Capacity MiB': '51,200' },
  ]), 'vDisk');

  const parsed = workbookToRequests(workbook);

  assert.equal(parsed.requests.length, 1);
  assert.equal(parsed.requests[0].environment, 'app-01');
  assert.match(parsed.warnings.join('\n'), /Skipped 1 VMware service\/system VMs/i);
  assert.match(parsed.warnings.join('\n'), /vCLS-123456/);
});

test('rvtools skipped service vm warning keeps the full explicit vm list', () => {
  const workbook = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(workbook, XLSX.utils.json_to_sheet([
    { VM: 'vCLS-a', Powerstate: 'poweredOn', Template: 'False', 'SRM Placeholder': 'False', CPUs: '2', Memory: '2048', 'Total disk capacity MiB': '10240', Cluster: 'cluster-a', 'OS according to the configuration file': 'Other Linux (64-bit)' },
    { VM: 'vCLS-b', Powerstate: 'poweredOn', Template: 'False', 'SRM Placeholder': 'False', CPUs: '2', Memory: '2048', 'Total disk capacity MiB': '10240', Cluster: 'cluster-a', 'OS according to the configuration file': 'Other Linux (64-bit)' },
    { VM: 'vCLS-c', Powerstate: 'poweredOn', Template: 'False', 'SRM Placeholder': 'False', CPUs: '2', Memory: '2048', 'Total disk capacity MiB': '10240', Cluster: 'cluster-a', 'OS according to the configuration file': 'Other Linux (64-bit)' },
    { VM: 'app-02', Powerstate: 'poweredOn', Template: 'False', 'SRM Placeholder': 'False', CPUs: '4', Memory: '8192', 'Total disk capacity MiB': '51200', Cluster: 'cluster-a', 'min Required EVC Mode Key': 'intel-cascadelake', 'OS according to the configuration file': 'Oracle Linux 8 (64-bit)' },
  ]), 'vInfo');
  XLSX.utils.book_append_sheet(workbook, XLSX.utils.json_to_sheet([
    { VM: 'vCLS-a', CPUs: '2' },
    { VM: 'vCLS-b', CPUs: '2' },
    { VM: 'vCLS-c', CPUs: '2' },
    { VM: 'app-02', CPUs: '4' },
  ]), 'vCPU');
  XLSX.utils.book_append_sheet(workbook, XLSX.utils.json_to_sheet([
    { VM: 'vCLS-a', 'Size MiB': '2048' },
    { VM: 'vCLS-b', 'Size MiB': '2048' },
    { VM: 'vCLS-c', 'Size MiB': '2048' },
    { VM: 'app-02', 'Size MiB': '8192' },
  ]), 'vMemory');
  XLSX.utils.book_append_sheet(workbook, XLSX.utils.json_to_sheet([
    { VM: 'vCLS-a', 'Capacity MiB': '10240' },
    { VM: 'vCLS-b', 'Capacity MiB': '10240' },
    { VM: 'vCLS-c', 'Capacity MiB': '10240' },
    { VM: 'app-02', 'Capacity MiB': '51200' },
  ]), 'vDisk');

  const parsed = workbookToRequests(workbook);
  const joined = parsed.warnings.join('\n');
  assert.match(joined, /vCLS-a, vCLS-b, vCLS-c/);
  assert.doesNotMatch(joined, /and \d+ more/);
});

test('guided workbook analysis returns processor choices and quotable row count', () => {
  const sheet = XLSX.utils.json_to_sheet([
    {
      HW: 'Servidor',
      'Nombre Equipo': 'guided-01',
      CPU: '2 x Intel(R) Xeon(R) CPU E5-2690 v4 @ 2.60GHz',
      Cores: '14',
      'Memoria Gb': '256',
      'Aprovisionado Gb': '121.2',
      SO: 'Oracle Linux 7',
    },
  ]);
  const workbook = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(workbook, sheet, 'Bare Metal to OCI');

  const analysis = analyzeWorkbookForGuidedQuote(workbook);

  assert.equal(analysis.sourceType, 'inventory_workbook');
  assert.equal(analysis.quotableRows, 1);
  assert.deepEqual(analysis.sourcePlatformOptions.map((item) => item.value), ['bare_metal', 'vmware', 'other_hypervisor']);
  assert.deepEqual(analysis.processorOptions.map((item) => item.value), ['intel', 'amd', 'ampere']);
});

test('guided workbook flow exposes flex shapes only for selected processor', () => {
  const amdShapes = buildShapeOptionsForProcessor('amd').map((item) => item.value);
  const intelShapes = buildShapeOptionsForProcessor('intel').map((item) => item.value);

  assert.deepEqual(intelShapes, ['VM.STANDARD3.FLEX', 'VM.OPTIMIZED3.FLEX']);
  assert.ok(amdShapes.includes('VM.STANDARD.E4.FLEX'));
  assert.ok(amdShapes.includes('VM.DENSEIO.E5.FLEX'));
  assert.ok(!amdShapes.includes('VM.STANDARD2.4'));
});

test('guided workbook selection applies chosen processor and flex shape to generated requests', () => {
  const sheet = XLSX.utils.json_to_sheet([
    {
      HW: 'Servidor',
      'Nombre Equipo': 'guided-02',
      CPU: '2 x Intel(R) Xeon(R) CPU E5-2690 v4 @ 2.60GHz',
      Cores: '14',
      'Memoria Gb': '256',
      'Aprovisionado Gb': '121.2',
      SO: 'Oracle Linux 7',
    },
  ]);
  const workbook = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(workbook, sheet, 'Bare Metal to OCI');

  const parsed = workbookToRequests(workbook, {
    sourcePlatform: 'bare_metal',
    processorVendor: 'amd',
    shapeName: 'VM.Standard.E4.Flex',
  });

  assert.equal(parsed.requests.length, 1);
  assert.match(parsed.requests[0].source, /Quote VM\.Standard\.E4\.Flex 28 OCPUs 256 GB RAM with 121\.2 GB Block Storage/);
  assert.equal(parsed.requests[0].processorVendor, 'amd');
  assert.equal(parsed.requests[0].shape.shapeName, 'VM.STANDARD.E4.FLEX');
  assert.match(parsed.warnings.join('\n'), /selected OCI target shape `VM\.Standard\.E4\.Flex` on AMD compute/i);
});

test('inventory workbook uses different CPU sizing for bare metal and vmware source platforms', () => {
  const sheet = XLSX.utils.json_to_sheet([
    {
      HW: 'Servidor',
      'Nombre Equipo': 'guided-03',
      CPU: '2 x Intel(R) Xeon(R) CPU E5-2690 v4 @ 2.60GHz',
      Cores: '14',
      'Memoria Gb': '256',
      'Aprovisionado Gb': '121.2',
      SO: 'Oracle Linux 7',
    },
  ]);
  const workbook = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(workbook, sheet, 'Bare Metal to OCI');

  const bareMetal = workbookToRequests(workbook, {
    sourcePlatform: 'bare_metal',
    processorVendor: 'intel',
    shapeName: 'VM.Standard3.Flex',
  });
  const vmware = workbookToRequests(workbook, {
    sourcePlatform: 'vmware',
    processorVendor: 'intel',
    shapeName: 'VM.Standard3.Flex',
  });
  const otherHypervisor = workbookToRequests(workbook, {
    sourcePlatform: 'other_hypervisor',
    processorVendor: 'intel',
    shapeName: 'VM.Standard3.Flex',
  });

  assert.equal(bareMetal.requests[0].ocpus, 28);
  assert.equal(vmware.requests[0].ocpus, 14);
  assert.equal(otherHypervisor.requests[0].ocpus, 14);
  assert.match(bareMetal.warnings.join('\n'), /bare metal inventory/i);
  assert.match(vmware.warnings.join('\n'), /vmware virtual machines/i);
  assert.match(otherHypervisor.warnings.join('\n'), /another hypervisor/i);
});

test('workbook follow-up parser detects spanish VPU overrides from short chat messages', () => {
  const selection = parseWorkbookPromptSelections("SI cambiamos el block storage a 20VPU's como se veria este quote?");

  assert.equal(selection.vpuPerGb, 20);
  assert.equal(selection.shapeName, '');
  assert.equal(selection.processorVendor, null);
  assert.equal(selection.sourcePlatform, null);
  assert.equal(hasWorkbookSelection(selection), true);
});
