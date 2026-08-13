import type { ExecutionDetail } from "@/lib/types";
import { ExecutionStatusBadge } from "@/components/ui/Badge";
import { formatRelativeTime } from "@/lib/format";
import ToolCallItem from "./ToolCall";
import CodeChangeItem from "./CodeChange";
import TestResultItem from "./TestResult";

/** The full record for one execution — used by the history view. Unlike
 * AgentActivity (the live right-hand panel), this never polls: it's
 * shown for a specific, already-fetched ExecutionDetail, active or not.
 */
export default function ExecutionDetails({ execution }: { execution: ExecutionDetail }) {
  return (
    <div className="flex flex-col gap-4">
      <div>
        <div className="flex items-center gap-2">
          <ExecutionStatusBadge status={execution.status} />
          <span className="text-xs text-faint">
            started {formatRelativeTime(execution.started_at)}
          </span>
        </div>
        <p className="mt-2 text-sm text-text">{execution.user_request}</p>
        {execution.retry_count > 0 && (
          <p className="mt-1 text-xs text-muted">
            {execution.retry_count} retry attempt{execution.retry_count === 1 ? "" : "s"}
          </p>
        )}
      </div>

      {execution.error_message && (
        <Section title="Error">
          <p className="rounded bg-danger/10 p-2 text-xs text-danger">
            {execution.error_message}
          </p>
        </Section>
      )}

      {execution.agent_plans.length > 0 && (
        <Section title="Plan">
          <pre className="whitespace-pre-wrap rounded bg-panel-alt p-2 text-xs text-muted">
            {execution.agent_plans[execution.agent_plans.length - 1].plan}
          </pre>
        </Section>
      )}

      {execution.tool_calls.length > 0 && (
        <Section title={`Tool calls (${execution.tool_calls.length})`}>
          <div className="flex flex-col gap-1.5">
            {execution.tool_calls.map((toolCall) => (
              <ToolCallItem key={toolCall.id} toolCall={toolCall} />
            ))}
          </div>
        </Section>
      )}

      {execution.code_changes.length > 0 && (
        <Section title={`Code changes (${execution.code_changes.length})`}>
          <div className="flex flex-col gap-1.5">
            {execution.code_changes.map((change) => (
              <CodeChangeItem key={change.id} change={change} />
            ))}
          </div>
        </Section>
      )}

      {execution.test_results.length > 0 && (
        <Section title="Tests">
          <div className="flex flex-col gap-1.5">
            {execution.test_results.map((result) => (
              <TestResultItem key={result.id} result={result} />
            ))}
          </div>
        </Section>
      )}
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wide text-faint">
        {title}
      </p>
      {children}
    </div>
  );
}
