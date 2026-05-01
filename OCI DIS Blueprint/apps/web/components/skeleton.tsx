/* Skeleton loading primitives matching the app design system. */

type SkeletonProps = {
  className?: string;
};

export function Skeleton({ className = "" }: SkeletonProps): JSX.Element {
  return <div className={`skeleton ${className}`.trim()} aria-hidden="true" />;
}

export function SkeletonText({
  lines = 1,
  className = "",
}: {
  lines?: number;
  className?: string;
}): JSX.Element {
  return (
    <div className={`space-y-2 ${className}`.trim()}>
      {Array.from({ length: lines }).map((_, index) => (
        <Skeleton
          key={index}
          className={`h-4 ${index === lines - 1 && lines > 1 ? "w-3/4" : "w-full"}`}
        />
      ))}
    </div>
  );
}

export function SkeletonRow(): JSX.Element {
  return (
    <tr className="animate-pulse">
      <td className="px-3 py-3"><Skeleton className="h-4 w-5" /></td>
      <td className="px-3 py-3">
        <Skeleton className="mb-2 h-4 w-36" />
        <Skeleton className="h-3 w-32" />
      </td>
      <td className="px-3 py-3"><Skeleton className="h-4 w-40" /></td>
      <td className="px-3 py-3"><Skeleton className="h-6 w-28 rounded-md" /></td>
      <td className="px-3 py-3"><Skeleton className="h-6 w-16 rounded-md" /></td>
      <td className="px-3 py-3"><Skeleton className="h-6 w-16 rounded-md" /></td>
      <td className="px-3 py-3"><Skeleton className="ml-auto h-4 w-8" /></td>
    </tr>
  );
}
