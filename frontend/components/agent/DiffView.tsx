/** Renders an already-computed unified diff by colorizing +/-/@@ lines.
 * No diff library needed — the backend computes the diff itself
 * (app/core/diff.py's unified_file_diff), both for already-applied
 * CodeChange rows and for a pending TaskResponse.proposed_changes entry;
 * this only has to render text that's already in unified-diff format.
 */
export default function DiffView({ diff }: { diff: string }) {
  const lines = diff.split("\n");
  return (
    <pre className="max-h-96 overflow-auto rounded bg-bg p-2 font-mono text-[11px] leading-5">
      {lines.map((line, i) => {
        let lineClass = "text-muted";
        if (line.startsWith("+++") || line.startsWith("---")) lineClass = "text-faint";
        else if (line.startsWith("+")) lineClass = "bg-success/10 text-success";
        else if (line.startsWith("-")) lineClass = "bg-danger/10 text-danger";
        else if (line.startsWith("@@")) lineClass = "text-info";
        return (
          <div key={i} className={`whitespace-pre px-1 ${lineClass}`}>
            {line || " "}
          </div>
        );
      })}
    </pre>
  );
}
