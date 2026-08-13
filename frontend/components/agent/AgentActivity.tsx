"use client";

import { useExecution } from "@/hooks/useExecution";
import { ExecutionStatusBadge } from "@/components/ui/Badge";
import { LoadingRow } from "@/components/ui/Loading";
import EmptyState from "@/components/ui/EmptyState";
import ToolCallItem from "./ToolCall";
import CodeChangeItem from "./CodeChange";
import TestResultItem from "./TestResult";
import ApprovalPanel from "./ApprovalPanel";
import { formatRelativeTime } from "@/lib/format";

/**
 * The right-hand panel — a live feed built entirely from
 * GET /api/executions/{id} (polled by useExecution while the run is
 * active). Nothing here is a fixed "Planning / Searching / Modifying"
 * checklist with fabricated step names — each section only appears once
 * the corresponding data actually exists, which is both simpler and more
 * honest than pretending to know internal LangGraph node names.
 */
export default function AgentActivity({ executionId }: { executionId: string | null }) {
  const { execution, loading, error, refresh } = useExecution(executionId);

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-border px-3 py-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-muted">
          Agent Activity
        </span>
      </div>

      <div className="flex-1 overflow-y-auto p-3">
        {!executionId && (
          <EmptyState
            title="No active execution."
            description="Send a message to see the agent at work."
          />
        )}

        {executionId && loading && !execution && <LoadingRow label="Loading…" />}

        {error && <p className="text-xs text-danger">{error}</p>}

        {execution && (
          <div className="flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <ExecutionStatusBadge status={execution.status} />
              <span className="text-[11px] text-faint">
                {formatRelativeTime(execution.started_at)}
              </span>
            </div>

            <p className="text-xs text-muted">{execution.user_request}</p>

            {execution.status === "waiting_for_approval" && (
              <ApprovalPanel executionId={execution.id} onDecided={refresh} />
            )}

            {execution.status === "failed" && execution.error_message && (
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
        )}
      </div>
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
