'use strict';

const XLSX = require('xlsx');

function parseWorkbookBase64(contentBase64) {
  const buffer = Buffer.from(contentBase64, 'base64');
  const workbook = XLSX.read(buffer, { type: 'buffer', cellDates: false, cellFormula: false });
  return workbook;
}

function workbookToRequests(workbook) {
  if (isRvToolsWorkbook(workbook)) {
    return rvToolsWorkbookToRequests(workbook);
  }

  const requests = [];
  const warnings = [];

  for (const sheetName of workbook.SheetNames) {
    const sheet = workbook.Sheets[sheetName];
    const rows = XLSX.utils.sheet_to_json(sheet, { defval: '', raw: false });
    if (!rows.length) continue;

    const normalizedMaps = rows.map((row) => normalizeRowKeys(row));

    if (isInventoryWorkbookSheet(normalizedMaps)) {
      const inventory = inventorySheetToRequests(sheetName, normalizedMaps);
      requests.push(...inventory.requests);
      warnings.push(...inventory.warnings);
      continue;
    }

    const normalizedRows = normalizedMaps.map((row) => normalizeRow(row));
    for (const row of normalizedRows) {
      if (!row.productQuery) continue;
      if (Array.isArray(row.importWarnings)) warnings.push(...row.importWarnings);
      requests.push({
        source: `Sheet ${sheetName}`,
        productQuery: row.productQuery,
        quantity: row.quantity,
        instances: row.instances,
        hours: row.hours,
        environment: row.environment || sheetName,
        currencyCode: row.currencyCode || 'USD',
        explicitPartNumber: row.explicitPartNumber,
        modifiers: {
          capacityReservationUtilization: row.capacityReservationUtilization,
          preemptible: row.preemptible,
          burstableBaseline: row.burstableBaseline,
        },
      });
    }
  }

  return {
    requests,
    warnings: dedupe(warnings),
  };
}

function isRvToolsWorkbook(workbook) {
  const names = new Set((workbook?.SheetNames || []).map((name) => String(name || '').toLowerCase()));
  return names.has('vinfo') && names.has('vcpu') && names.has('vmemory');
}

function rvToolsWorkbookToRequests(workbook) {
  const requests = [];
  const warnings = [];
  const vInfoRows = getNormalizedSheetRows(workbook, 'vInfo');
  const vCpuRows = getNormalizedSheetRows(workbook, 'vCPU');
  const vMemoryRows = getNormalizedSheetRows(workbook, 'vMemory');
  const vDiskRows = getNormalizedSheetRows(workbook, 'vDisk');
  const stats = {
    skippedServiceVmNames: [],
    poweredOffVmNames: [],
    windowsVmNames: [],
  };

  const cpuByVm = new Map(vCpuRows.map((row) => [asString(row.vm), row]).filter(([vm]) => vm));
  const memoryByVm = new Map(vMemoryRows.map((row) => [asString(row.vm), row]).filter(([vm]) => vm));
  const disksByVm = new Map();
  for (const row of vDiskRows) {
    const vm = asString(row.vm);
    if (!vm) continue;
    if (!disksByVm.has(vm)) disksByVm.set(vm, []);
    disksByVm.get(vm).push(row);
  }

  for (const infoRow of vInfoRows) {
    const normalized = normalizeRvToolsVm(infoRow, {
      cpuByVm,
      memoryByVm,
      disksByVm,
    });
    if (!normalized) continue;
    if (normalized.skipped) {
      if (normalized.skipReason === 'vmware-service-vm' && normalized.vmName) {
        stats.skippedServiceVmNames.push(normalized.vmName);
      }
      continue;
    }
    requests.push(normalized.request);
    if (normalized.metadata?.poweredOff && normalized.vmName) stats.poweredOffVmNames.push(normalized.vmName);
    if (normalized.metadata?.windows && normalized.vmName) stats.windowsVmNames.push(normalized.vmName);
  }

  if (requests.length) {
    warnings.unshift('RVTools workbook detected. The agent mapped VMware VM inventory into OCI-native compute plus block storage estimates using configured vCPU, memory, and provisioned disk capacity.');
    warnings.push('For VMware x86 workloads, the import converts 2 VMware vCPUs to 1 OCI OCPU because OCI OCPUs represent physical cores with 2 threads.');
  }
  if (stats.skippedServiceVmNames.length) {
    warnings.push(`Skipped ${stats.skippedServiceVmNames.length} VMware service/system VMs that should not be migration-priced: ${previewNames(stats.skippedServiceVmNames)}.`);
  }
  if (stats.poweredOffVmNames.length) {
    warnings.push(`Included ${stats.poweredOffVmNames.length} powered-off VMs using configured VMware resources for migration sizing: ${previewNames(stats.poweredOffVmNames)}.`);
  }
  if (stats.windowsVmNames.length) {
    warnings.push(`Detected ${stats.windowsVmNames.length} Windows VMs. This pass prices OCI compute and storage, but does not add separate Windows licensing adjustments: ${previewNames(stats.windowsVmNames)}.`);
  }

  return {
    requests,
    warnings: dedupe(warnings),
  };
}

function normalizeRow(row) {
  const productQuery = asString(
    row.product || row.service || row.sku || row.partnumber || row.partno || row.displayname || row.item,
  );
  const explicitPartNumber = extractPartNumber(productQuery) || extractPartNumber(asString(row.partnumber || row.partno || row.sku));

  return {
    productQuery,
    explicitPartNumber,
    quantity: asNumber(row.qty || row.quantity || row.metricqty || row.ocpu || row.ecpu || row.gb || row.storage || 1),
    instances: asNumber(row.instances || row.instance || row.nodes || row.vm || 1),
    hours: asNumber(row.hours || row.monthlyuptime || row.uptime || 744),
    environment: asString(row.environment || row.env),
    currencyCode: asString(row.currency || row.currencycode).toUpperCase() || 'USD',
    capacityReservationUtilization: nullableNumber(row.capacityreservation || row.reservation || row.capacityreservationutilization),
    preemptible: truthy(row.preemptible),
    burstableBaseline: nullableNumber(row.burstable || row.baseline || row.burstablebaseline),
  };
}

function normalizeRvToolsVm(infoRow, context) {
  const vmName = asString(infoRow.vm);
  if (!vmName) return null;
  if (truthy(infoRow.template) || truthy(infoRow.srmplaceholder)) return null;
  if (isVmwareServiceVm(infoRow)) {
    return {
      skipped: true,
      skipReason: 'vmware-service-vm',
      vmName,
    };
  }

  const cpuRow = context.cpuByVm.get(vmName) || {};
  const memoryRow = context.memoryByVm.get(vmName) || {};
  const diskRows = context.disksByVm.get(vmName) || [];

  const vcpus = nullableNumber(cpuRow.cpus || infoRow.cpus);
  const memoryMib = nullableNumber(memoryRow.sizemib || infoRow.memory);
  const totalDiskMib = sumNumbers(diskRows.map((row) => row.capacitymib)) ||
    nullableNumber(infoRow.totaldiskcapacitymib) ||
    nullableNumber(infoRow.provisionedmib);

  if (!vcpus || !memoryMib) return null;

  const processorVendor = inferRvToolsVendor(infoRow, cpuRow);
  const shapeSeries = inferInventoryShapeSeries(processorVendor);
  const ocpus = mapVmwareVcpusToOcpus(vcpus, processorVendor);
  const memoryGb = roundQuantity(memoryMib / 1024);
  const capacityGb = totalDiskMib ? roundQuantity(totalDiskMib / 1024) : null;
  const osName = asString(
    infoRow.osaccordingtothevmwaretools ||
    infoRow.osaccordingtotheconfigurationfile,
  );
  const clusterName = asString(infoRow.cluster);
  const powerState = asString(infoRow.powerstate).toLowerCase();
  const isWindows = !!(osName && /windows/i.test(osName));

  const sourceParts = [`Quote ${shapeSeries} ${ocpus} OCPUs ${memoryGb} GB RAM`];
  if (capacityGb) sourceParts.push(`with ${capacityGb} GB Block Storage`);
  const source = sourceParts.join(' ');

  return {
    request: {
      source,
      productQuery: source,
      serviceFamily: 'compute_flex',
      shape: {
        kind: 'flex',
        family: 'standard',
        series: shapeSeries.replace(/\.flex$/i, '').toUpperCase(),
      },
      shapeSeries,
      processorVendor,
      quantity: Number(ocpus),
      ocpus: Number(ocpus),
      memoryQuantity: memoryGb,
      capacityGb,
      instances: 1,
      hours: 744,
      environment: vmName,
      currencyCode: 'USD',
      modifiers: {},
      metadata: {
        inventorySource: 'rvtools',
        cluster: clusterName || null,
        vmwareVcpus: Number(vcpus),
      },
    },
    vmName,
    metadata: {
      poweredOff: powerState && powerState !== 'poweredon',
      windows: isWindows,
    },
  };
}

function isInventoryWorkbookSheet(rows) {
  if (!rows.length) return false;
  return rows.some((row) => {
    const hasCpu = asString(row.cpu);
    const hasMemory = asString(row.memoriagb || row.memorygb || row.memory);
    const hasCores = asString(row.cores);
    const hasHost = asString(row.nombreequipo || row.hostname || row.servername);
    return !!(hasCpu && hasMemory && hasCores && hasHost);
  });
}

function inventorySheetToRequests(sheetName, rows) {
  const requests = [];
  const warnings = [];

  for (const row of rows) {
    const normalized = normalizeInventoryRow(row);
    if (!normalized) continue;
    requests.push(normalized.request);
    warnings.push(...normalized.warnings);
  }

  return {
    requests,
    warnings: dedupe(warnings),
  };
}

function normalizeInventoryRow(row) {
  const host = asString(row.nombreequipo || row.hostname || row.servername || row.ipequipo);
  const hwType = asString(row.hw);
  const cpuText = asString(row.cpu);
  const osName = asString(row.so);
  const memoryGb = nullableNumber(row.memoriagb || row.memorygb || row.memory);
  const coresPerSocket = nullableNumber(row.cores);
  const provisionedGb = nullableNumber(row.aprovisionadogb || row.provisionedgb || row.storagegb || row.discousadogb);

  if (!cpuText || !memoryGb || !coresPerSocket) return null;
  if (/^total$/i.test(host) || /^total$/i.test(hwType)) return null;
  if (/shared across/i.test(host) || /shared across/i.test(hwType)) return null;
  if (hwType && !/servidor|server/i.test(hwType)) return null;

  const socketCount = inferSocketCount(cpuText);
  const processorVendor = inferProcessorVendor(cpuText);
  const shapeSeries = inferInventoryShapeSeries(processorVendor);
  const ocpus = socketCount * Number(coresPerSocket);
  if (!Number.isFinite(ocpus) || ocpus <= 0) return null;

  const sourceParts = [
    `Quote ${shapeSeries} ${ocpus} OCPUs ${memoryGb} GB RAM`,
  ];
  if (Number.isFinite(Number(provisionedGb)) && Number(provisionedGb) > 0) {
    sourceParts.push(`with ${provisionedGb} GB Block Storage`);
  }
  const source = sourceParts.join(' ');

  const requestWarnings = [
    `Workbook inventory rows were mapped heuristically to OCI ${shapeSeries} based on detected ${processorVendor.toUpperCase()} CPU inventory data.`,
  ];
  if (osName && /windows/i.test(osName)) {
    requestWarnings.push(`Workbook row "${host || 'unknown host'}" uses ${osName}; this estimate currently prices OCI compute and storage only, without separate Windows licensing adjustments.`);
  }

  return {
    request: {
      source,
      productQuery: source,
      serviceFamily: 'compute_flex',
      shape: {
        kind: 'flex',
        family: 'standard',
        series: shapeSeries.replace(/\.flex$/i, '').toUpperCase(),
      },
      shapeSeries,
      processorVendor,
      quantity: ocpus,
      ocpus,
      memoryQuantity: Number(memoryGb),
      capacityGb: Number.isFinite(Number(provisionedGb)) ? Number(provisionedGb) : null,
      instances: 1,
      hours: 744,
      environment: host || sheetName,
      currencyCode: 'USD',
      modifiers: {},
      metadata: {
        inventorySource: 'inventory_workbook',
      },
    },
    warnings: requestWarnings,
  };
}

function inferSocketCount(cpuText) {
  const direct = String(cpuText || '').match(/(^|\b)(\d+)\s*x\b/i);
  if (direct) {
    const count = Number(direct[2]);
    if (Number.isFinite(count) && count > 0) return count;
  }
  return 1;
}

function inferProcessorVendor(cpuText) {
  const source = String(cpuText || '').toLowerCase();
  if (/\bamd\b|epyc/.test(source)) return 'amd';
  if (/\barm\b|ampere/.test(source)) return 'arm';
  return 'intel';
}

function inferRvToolsVendor(infoRow, cpuRow) {
  const source = [
    infoRow.minrequiredevcmodekey,
    infoRow.guestdetaileddata,
    cpuRow.annotation,
    infoRow.annotation,
  ].map((value) => asString(value).toLowerCase()).join(' ');
  if (/\bamd\b|epyc/.test(source)) return 'amd';
  if (/\barm\b|ampere/.test(source)) return 'arm';
  return 'intel';
}

function isVmwareServiceVm(infoRow) {
  const vmName = asString(infoRow.vm);
  const clusterName = asString(infoRow.cluster);
  const source = [
    vmName,
    infoRow.annotation,
    infoRow.osaccordingtotheconfigurationfile,
    infoRow.osaccordingtothevmwaretools,
  ].map((value) => asString(value).toLowerCase()).join(' ');

  if (/^vcls-/i.test(vmName)) return true;
  if (/\b(vcenter|vcsa|platform services controller|psc|site recovery manager|srm|vrealize|vrops|vrli|nsx|hcx|wcp|tanzu)\b/i.test(source)) {
    return true;
  }
  if (/^domain-c\d+/i.test(vmName) && /^ha-datacenter/i.test(clusterName)) return true;
  return false;
}

function inferInventoryShapeSeries(processorVendor) {
  if (processorVendor === 'arm') return 'A1.Flex';
  if (processorVendor === 'amd') return 'E5.Flex';
  return 'E4.Flex';
}

function mapVmwareVcpusToOcpus(vcpus, processorVendor) {
  const count = Number(vcpus);
  if (!Number.isFinite(count) || count <= 0) return null;
  if (processorVendor === 'arm') return count;
  return Math.max(1, Math.ceil(count / 2));
}

function normalizeKey(value) {
  return String(value || '').toLowerCase().replace(/[^a-z0-9]+/g, '');
}

function normalizeRowKeys(row) {
  const normalized = {};
  for (const [key, value] of Object.entries(row || {})) {
    const normalizedKey = normalizeKey(key);
    if (!normalizedKey) continue;
    normalized[normalizedKey] = mergeNormalizedValues(normalized[normalizedKey], value);
  }
  return normalized;
}

function getNormalizedSheetRows(workbook, sheetName) {
  const sheetKey = (workbook?.SheetNames || []).find((name) => String(name || '').toLowerCase() === String(sheetName || '').toLowerCase());
  if (!sheetKey) return [];
  const sheet = workbook.Sheets[sheetKey];
  if (!sheet) return [];
  return XLSX.utils.sheet_to_json(sheet, { defval: '', raw: false }).map((row) => normalizeRowKeys(row));
}

function mergeNormalizedValues(current, incoming) {
  if (current === undefined || current === null || current === '') return incoming;
  const currentNumber = nullableNumber(current);
  const incomingNumber = nullableNumber(incoming);
  if (currentNumber !== null && incomingNumber !== null) {
    return Math.max(currentNumber, incomingNumber);
  }
  const currentText = asString(current);
  const incomingText = asString(incoming);
  return incomingText.length > currentText.length ? incoming : current;
}

function asString(value) {
  return String(value || '').trim();
}

function asNumber(value) {
  const num = Number(String(value || '').replace(/,/g, '').trim());
  return Number.isFinite(num) ? num : 1;
}

function nullableNumber(value) {
  const normalized = String(value || '').trim();
  if (!normalized || normalized === '-') return null;
  const num = Number(normalized.replace(/,/g, ''));
  return Number.isFinite(num) ? num : null;
}

function truthy(value) {
  const normalized = String(value || '').trim().toLowerCase();
  return ['y', 'yes', 'true', '1', 'x'].includes(normalized);
}

function extractPartNumber(value) {
  const match = String(value || '').match(/\b(B\d{5,})\b/i);
  return match ? match[1].toUpperCase() : null;
}

function sumNumbers(values) {
  const total = (values || []).reduce((acc, value) => {
    const num = nullableNumber(value);
    return num === null ? acc : acc + num;
  }, 0);
  return total > 0 ? total : null;
}

function roundQuantity(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) return null;
  return Number(num.toFixed(3));
}

function previewNames(names, limit = 8) {
  const items = dedupe(names);
  if (items.length <= limit) return items.join(', ');
  return `${items.slice(0, limit).join(', ')} and ${items.length - limit} more`;
}

function dedupe(items) {
  return Array.from(new Set((items || []).filter(Boolean)));
}

module.exports = {
  parseWorkbookBase64,
  workbookToRequests,
};
