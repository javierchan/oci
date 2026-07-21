/* Small, dependency-free formatter for bounded model narratives. */

export type GovernedNarrativeBlock =
  | { kind: "heading" | "paragraph"; text: string }
  | { kind: "list"; ordered: boolean; items: string[]; start?: number }
  | { kind: "notice"; text: string };

const MAX_BLOCKS = 24;

function stripInlineMarkdown(value: string): string {
  return value
    .replace(/^#{1,4}\s*/, "")
    .replace(/\*\*(.*?)\*\*/g, "$1")
    .replace(/__(.*?)__/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\s*[–-]\s*\[REDACTED\]\s*$/i, "")
    .trim();
}

function parseInlineTable(content: string): GovernedNarrativeBlock[] | null {
  const pipeCount = (content.match(/\|/g) ?? []).length;
  if (pipeCount < 8) return null;

  const cells = content
    .replace(/\r?\n/g, " ")
    .split("|")
    .map((cell) => cell.trim())
    .filter((cell) => cell.length > 0 && !/^:?-{3,}:?$/.test(cell));
  const topicIndex = cells.findIndex((cell) => cell.toLowerCase() === "topic");
  const actionIndex = cells.findIndex((cell) => cell.toLowerCase() === "recommended action");
  if (topicIndex < 0 || actionIndex <= topicIndex) return null;

  const headers = cells.slice(topicIndex, actionIndex + 1).map(stripInlineMarkdown);
  const values = cells.slice(actionIndex + 1);
  if (headers.length < 2 || values.length < headers.length) return null;

  const blocks: GovernedNarrativeBlock[] = [];
  const intro = stripInlineMarkdown(cells.slice(0, topicIndex).join(" "));
  if (intro) blocks.push({ kind: "heading", text: intro });
  for (let index = 0; index + headers.length <= values.length && blocks.length < MAX_BLOCKS; index += headers.length) {
    const row = values.slice(index, index + headers.length).map(stripInlineMarkdown);
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

function narrativeLines(content: string): string[] {
  const lines = content
    .replace(/\r/g, "")
    .split(/\n+/)
    .flatMap((line) => {
      const pipeCount = (line.match(/\|/g) ?? []).length;
      if (pipeCount < 4) return [line];
      return line.split("|");
    })
    .map((line) => line.trim())
    .filter((line) => line.length > 0 && !/^:?-{3,}:?$/.test(line));

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

  const lines = narrativeLines(content);
  const blocks: GovernedNarrativeBlock[] = [];

  for (let lineIndex = 0; lineIndex < lines.length && lineIndex < MAX_BLOCKS; lineIndex += 1) {
    const line = lines[lineIndex];
    const bullet = line.match(/^[-•]\s+(.+)$/);
    const ordered = line.match(/^(\d+)[.)]\s+(.+)$/);
    const clean = stripInlineMarkdown(bullet?.[1] ?? ordered?.[2] ?? line);
    if (!clean) continue;

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

  if (lines.length > MAX_BLOCKS) {
    blocks.push({ kind: "notice", text: "Additional synthesis is available in the exported review." });
  }
  return blocks;
}
