import type { ExecutionSummary, Project } from "@/lib/types";
import { formatRelativeTime } from "@/lib/format";

/** Compact top bar for the workspace (spec section 16). "Status: Active"
 * is a constant, not a real field — the Project model has no
 * active/archived concept, so there's nothing to derive it from; every
 * project that exists is implicitly active.
 */
export default function ProjectOverview({
  project,
  lastExecution,
}: {
  project: Project;
  lastExecution?: ExecutionSummary;
}) {
  return (
    <div className="flex flex-wrap items-center gap-x-6 gap-y-1 border-b border-border bg-panel px-4 py-2 text-xs">
      <Field label="Project" value={project.name} />
      <Field label="Repository" value={project.repository_path} mono />
      <Field label="Status" value="Active" />
      {lastExecution && (
        <Field label="Last Execution" value={formatRelativeTime(lastExecution.started_at)} />
      )}
    </div>
  );
}

function Field({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-baseline gap-1.5">
      <span className="text-faint">{label}</span>
      <span className={`truncate text-text ${mono ? "font-mono" : ""}`}>{value}</span>
    </div>
  );
}
