import Link from "next/link";
import { ChevronRight } from "lucide-react";

type BreadcrumbItem = {
  label: string;
  href?: string;
};

type BreadcrumbProps = {
  items: BreadcrumbItem[];
};

export function Breadcrumb({ items }: BreadcrumbProps): JSX.Element {
  return (
    <nav aria-label="Breadcrumb" className="flex flex-wrap items-center gap-2 text-sm text-[var(--color-text-secondary)]">
      {items.map((item, index) => {
        const isLast = index === items.length - 1;
        return (
          <span key={`${item.label}-${index}`} className="inline-flex items-center gap-2">
            {index > 0 ? <ChevronRight className="h-4 w-4 text-[var(--color-text-muted)]" /> : null}
            {item.href && !isLast ? (
              <Link href={item.href} className="transition hover:text-[var(--color-text-primary)]">
                {item.label}
              </Link>
            ) : (
              <span className={isLast ? "font-medium text-[var(--color-text-primary)]" : undefined}>
                {item.label}
              </span>
            )}
          </span>
        );
      })}
    </nav>
  );
}
