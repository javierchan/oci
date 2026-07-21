/* Safe presentation for optional GenAI explanations and historical narrative output. */

import { parseGovernedNarrative } from "@/lib/governed-narrative";

export function GovernedNarrative({ content, compact = false }: { content: string; compact?: boolean }): JSX.Element {
  const blocks = parseGovernedNarrative(content);

  return (
    <div className={`${compact ? "space-y-3" : "space-y-4"} [overflow-wrap:anywhere]`}>
      {blocks.map((block, index) => {
        if (block.kind === "heading") {
          return <h5 key={`${block.kind}-${index}`} className="pt-0.5 text-sm font-semibold leading-5 text-[var(--color-text-primary)]">{block.text}</h5>;
        }
        if (block.kind === "list") {
          const List = block.ordered ? "ol" : "ul";
          return (
            <List
              key={`${block.kind}-${index}`}
              {...(block.ordered && block.start ? { start: block.start } : {})}
              className={`${block.ordered ? "list-decimal" : "list-disc"} space-y-1.5 pl-5 text-sm leading-6 text-[var(--color-text-secondary)] marker:font-semibold marker:text-[var(--color-accent)]`}
            >
              {block.items.map((item, itemIndex) => <li key={`${item}-${itemIndex}`} className="pl-1.5">{item}</li>)}
            </List>
          );
        }
        if (block.kind === "notice") {
          return <p key={`${block.kind}-${index}`} className="text-xs italic text-[var(--color-text-muted)]">{block.text}</p>;
        }
        return <p key={`${block.kind}-${index}`} className={`text-sm leading-6 ${index === 0 ? "text-[var(--color-text-primary)]" : "text-[var(--color-text-secondary)]"}`}>{block.text}</p>;
      })}
    </div>
  );
}
