/* Safe presentation for optional GenAI explanations and historical narrative output. */

import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { Fragment, type ReactNode } from "react";

import { parseGovernedNarrative } from "@/lib/governed-narrative";

const INLINE_MARKDOWN = /(\*\*[^*]+\*\*|\[[^\]]+\]\([^\s)]+\))/g;

function inlineContent(value: string): ReactNode[] {
  return value.split(INLINE_MARKDOWN).filter(Boolean).map((part, index) => {
    const bold = part.match(/^\*\*(.+)\*\*$/);
    if (bold) return <strong key={`${part}-${index}`} className="font-semibold text-[var(--color-text-primary)]">{bold[1]}</strong>;
    const link = part.match(/^\[([^\]]+)\]\(([^\s)]+)\)$/);
    if (link && link[2].startsWith("/") && !link[2].startsWith("//")) {
      return (
        <Link key={`${part}-${index}`} href={link[2]} className="inline-flex items-center gap-1 font-semibold text-[var(--color-accent)] underline decoration-transparent underline-offset-4 transition hover:decoration-current">
          {link[1]}<ArrowUpRight className="h-3.5 w-3.5" />
        </Link>
      );
    }
    return <Fragment key={`${part}-${index}`}>{part.replace(/\[([^\]]+)\]\([^\s)]+\)/g, "$1")}</Fragment>;
  });
}

export function GovernedNarrative({ content, compact = false }: { content: string; compact?: boolean }): JSX.Element {
  const blocks = parseGovernedNarrative(content);

  return (
    <div className={`${compact ? "space-y-3" : "space-y-4"} [overflow-wrap:anywhere]`}>
      {blocks.map((block, index) => {
        if (block.kind === "heading") {
          return <h5 key={`${block.kind}-${index}`} className="pt-0.5 text-sm font-semibold leading-5 text-[var(--color-text-primary)]">{inlineContent(block.text)}</h5>;
        }
        if (block.kind === "list") {
          const List = block.ordered ? "ol" : "ul";
          return (
            <List key={`${block.kind}-${index}`} {...(block.ordered && block.start ? { start: block.start } : {})} className={`${block.ordered ? "list-decimal" : "list-disc"} space-y-1.5 pl-5 text-sm leading-6 text-[var(--color-text-secondary)] marker:font-semibold marker:text-[var(--color-accent)]`}>
              {block.items.map((item, itemIndex) => <li key={`${item}-${itemIndex}`} className="pl-1.5">{inlineContent(item)}</li>)}
            </List>
          );
        }
        if (block.kind === "table") {
          return (
            <div key={`${block.kind}-${index}`} className="overflow-x-auto rounded-lg border border-[var(--color-border)]">
              <table className="min-w-full border-collapse text-left text-xs">
                <thead className="bg-[var(--color-surface-2)] text-[var(--color-text-primary)]"><tr>{block.headers.map((header) => <th key={header} className="border-b border-[var(--color-border)] px-3 py-2 font-semibold">{inlineContent(header)}</th>)}</tr></thead>
                <tbody className="divide-y divide-[var(--color-border)] text-[var(--color-text-secondary)]">{block.rows.map((row, rowIndex) => <tr key={`row-${rowIndex}`}>{row.map((cell, cellIndex) => <td key={`cell-${cellIndex}`} className="px-3 py-2 align-top leading-5">{inlineContent(cell)}</td>)}</tr>)}</tbody>
              </table>
            </div>
          );
        }
        if (block.kind === "notice") return <p key={`${block.kind}-${index}`} className="text-xs italic text-[var(--color-text-muted)]">{block.text}</p>;
        const isAction = /^(?:\*\*)?(?:next action|siguiente paso)(?:\*\*)?:/i.test(block.text);
        return <p key={`${block.kind}-${index}`} className={`${isAction ? "rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] px-3 py-2.5" : ""} text-sm leading-6 ${index === 0 ? "text-[var(--color-text-primary)]" : "text-[var(--color-text-secondary)]"}`}>{inlineContent(block.text)}</p>;
      })}
    </div>
  );
}
