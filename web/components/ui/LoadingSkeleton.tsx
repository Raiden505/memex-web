export default function LoadingSkeleton({ count = 3 }: { count?: number }) {
  return (
    <div className="flex flex-col gap-3">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="skeleton-pulse flex flex-col gap-2 p-4" style={{ minHeight: "64px" }}>
          <div className="h-3 rounded-full" style={{ width: `${60 + (i % 3) * 15}%`, background: "var(--color-surface-container-low)" }} />
          <div className="h-3 rounded-full" style={{ width: `${85 - (i % 3) * 10}%`, background: "var(--color-surface-container-low)" }} />
        </div>
      ))}
    </div>
  );
}
