/* Small, dependency-free formatter for bounded model narratives. */

export type GovernedNarrativeBlock =
  | { kind: "heading" | "paragraph"; text: string }
  | { kind: "list"; ordered: boolean; items: string[]; start?: number }
  | { kind: "table"; headers: string[]; rows: string[][] }
  | { kind: "notice"; text: string };

const MAX_BLOCKS = 24;
const TABLE_DIVIDER = /^\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?$/;

function normalizeText(value: string): string {
  return value
    .replace(/^#{1,4}\s*/, "")
    .replace(/\s*[–-]\s*\[REDACTED\]\s*$/i, "")
    .trim();
}

function tableCells(line: string): string[] {
  return line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => normalizeText(cell));
}

function parseInlineTable(content: string): GovernedNarrativeBlock[] | null {
  const pipeCount = (content.match(/\|/g) ?? []).length;
  if (pipeCount < 8 || content.includes("\n")) return null;

  const cells = content
    .split("|")
    .map((cell) => cell.trim())
    .filter((cell) => cell.length > 0 && !/^:?-{3,}:?$/.test(cell));
  const topicIndex = cells.findIndex((cell) => cell.toLowerCase() === "topic");
  const actionIndex = cells.findIndex((cell) => cell.toLowerCase() === "recommended action");
  if (topicIndex < 0 || actionIndex <= topicIndex) return null;

  const headers = cells.slice(topicIndex, actionIndex + 1).map(normalizeText);
  const values = cells.slice(actionIndex + 1);
  if (headers.length < 2 || values.length < headers.length) return null;

  const blocks: GovernedNarrativeBlock[] = [];
  const intro = normalizeText(cells.slice(0, topicIndex).join(" "));
  if (intro) blocks.push({ kind: "heading", text: intro });
  for (let index = 0; index + headers.length <= values.length && blocks.length < MAX_BLOCKS; index += headers.length) {
    const row = values.slice(index, index + headers.length).map(normalizeText);
    blocks.push({ kind: "heading", text: row[0] });
    headers.slice(1).forEach((header, headerIndex) => {
      if (blocks.length < MAX_BLOCKS && row[headerIndex + 1]) {
        blocks.push({ kind: "paragraph", text: `${header}: ${row[headerIndex + 1]}` });
      }
    });
  }
  if (values.length > Math.floor(values.length / headers.length) * headers.length || blocks.length >= MAX_BLOCKS) {
    blocks.push({ kind: "notice", text: "Additional synthesis is available in the exported review." });
  }
  return blocks;
}

function normalizedLines(content: string): string[] {
  const lines = content
    .replace(/\r/g, "")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  const normalized: string[] = [];
  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    const next = lines[index + 1];
    if (/^(?:\d+[.)]|[-•])$/.test(line) && next && !/^(?:\d+[.)]|[-•])(?:\s|$)/.test(next)) {
      normalized.push(`${line} ${next}`);
      index += 1;
    } else {
      normalized.push(line);
    }
  }
  return normalized;
}

export function parseGovernedNarrative(content: string): GovernedNarrativeBlock[] {
  const inlineTable = parseInlineTable(content);
  if (inlineTable) return inlineTable;

  const lines = normalizedLines(content);
  const blocks: GovernedNarrativeBlock[] = [];

  for (let lineIndex = 0; lineIndex < lines.length && blocks.length < MAX_BLOCKS; lineIndex += 1) {
    const line = lines[lineIndex];
    if (line.includes("|") && TABLE_DIVIDER.test(lines[lineIndex + 1] ?? "")) {
      const headers = tableCells(line);
      const rows: string[][] = [];
      lineIndex += 2;
      while (lineIndex < lines.length && lines[lineIndex].includes("|") && rows.length < 12) {
        const row = tableCells(lines[lineIndex]);
        rows.push(headers.map((_, index) => row[index] ?? ""));
        lineIndex += 1;
      }
      lineIndex -= 1;
      if (headers.length >= 2 && rows.length) blocks.push({ kind: "table", headers, rows });
      continue;
    }

    const bullet = line.match(/^[-•]\s+(.+)$/);
    const ordered = line.match(/^(\d+)[.)]\s+(.+)$/);
    const clean = normalizeText(bullet?.[1] ?? ordered?.[2] ?? line);
    if (!clean || TABLE_DIVIDER.test(clean)) continue;

    if (bullet || ordered) {
      const isOrdered = Boolean(ordered);
      const previous = blocks.at(-1);
      if (previous?.kind === "list" && previous.ordered === isOrdered) {
        previous.items.push(clean);
      } else {
        blocks.push({
          kind: "list",
          ordered: isOrdered,
          items: [clean],
          ...(ordered ? { start: Number(ordered[1]) } : {}),
        });
      }
    } else if (/^#{1,4}\s+/.test(line) || (clean.endsWith(":") && clean.length < 64)) {
      blocks.push({ kind: "heading", text: clean.replace(/:$/, "") });
    } else {
      blocks.push({ kind: "paragraph", text: clean });
    }
  }

  if (blocks.length >= MAX_BLOCKS || lines.length > MAX_BLOCKS * 2) {
    blocks.push({ kind: "notice", text: "Additional synthesis is available in the exported review." });
  }
  return blocks;
}
