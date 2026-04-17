"use client";

import { useState } from "react";

type TruncatedCellProps = {
  value: string;
  maxLength?: number;
};

export function TruncatedCell({
  value,
  maxLength = 120,
}: TruncatedCellProps): JSX.Element {
  const [expanded, setExpanded] = useState(false);
  const isLong = value.length > maxLength;

  if (!isLong) {
    return <span>{value}</span>;
  }

  return (
    <span>
      {expanded ? value : `${value.slice(0, maxLength)}…`}
      <button
        type="button"
        onClick={() => setExpanded((previous) => !previous)}
        className="ml-2 text-xs font-medium text-[var(--color-accent)] underline underline-offset-2 hover:opacity-80"
      >
        {expanded ? "Show less" : "Show full"}
      </button>
    </span>
  );
}
