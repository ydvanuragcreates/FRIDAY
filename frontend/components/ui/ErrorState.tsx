import Button from "./Button";

/** A consistent "something went wrong" panel — used for failed initial
 * fetches (backend unreachable, 404, network timeout, ...) so the UI
 * never just sits there silently stuck. `onRetry`, when given, re-runs
 * whatever fetch failed.
 */
export default function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 px-6 py-12 text-center">
      <p className="text-sm font-medium text-danger">Something went wrong</p>
      <p className="max-w-sm text-sm text-muted">{message}</p>
      {onRetry && (
        <Button variant="secondary" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}
