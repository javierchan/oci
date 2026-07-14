/* Safe presentation for optional GenAI explanations and historical narrative output. */

import { parseGovernedNarrative } from "@/lib/governed-narrative";

export function GovernedNarrative({ content, compact = false }: { content: string; compact?: boolean }): JSX.Element {
  const blocks = parseGovernedNarrative(content);

  return (
    <div className={`${compact ? "space-y-2" : "space-y-3"} [overflow-wrap:anywhere]`}>
      {blocks.map((block, index) => {
        if (block.kind === "heading") {
          return <h5 key={`${block.kind}-${index}`} className="pt-1 text-sm font-semibold text-[var(--color-text-primary)]">{block.text}</h5>;
        }
        if (block.kind === "bullet" || block.kind === "ordered") {
          return (
            <div key={`${block.kind}-${index}`} className="flex gap-2.5 text-sm leading-6 text-[var(--color-text-secondary)]">
              <span className="mt-[0.65rem] h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--color-accent)]" />
              <p>{block.text}</p>
            </div>
          );
        }
        if (block.kind === "notice") {
          return <p key={`${block.kind}-${index}`} className="text-xs italic text-[var(--color-text-muted)]">{block.text}</p>;
        }
        return <p key={`${block.kind}-${index}`} className="text-sm leading-6 text-[var(--color-text-secondary)]">{block.text}</p>;
      })}
    </div>
  );
}
