export function Spinner({ size = 16 }: { size?: number }) {
  return (
    <svg
      className="animate-spin text-current"
      style={{ width: size, height: size }}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="3"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8v3a5 5 0 00-5 5H4z"
      />
    </svg>
  );
}

/** A loading line/block sized to look roughly like the content it's
 * standing in for — used for lists (projects, conversations, messages)
 * while the initial fetch is in flight.
 */
export function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div className={`animate-pulse rounded-md bg-panel-alt ${className}`} />
  );
}

export function LoadingRow({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-2 px-3 py-6 text-sm text-muted">
      <Spinner size={14} />
      <span>{label}</span>
    </div>
  );
}
