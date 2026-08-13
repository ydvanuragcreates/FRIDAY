"use client";

import { useState } from "react";
import { useExecution, useExecutionHistory } from "@/hooks/useExecution";
import { ExecutionStatusBadge } from "@/components/ui/Badge";
import { Skeleton, LoadingRow } from "@/components/ui/Loading";
import EmptyState from "@/components/ui/EmptyState";
import ErrorState from "@/components/ui/ErrorState";
import { formatRelativeTime } from "@/lib/format";
import ExecutionDetails from "./ExecutionDetails";

export default function ExecutionHistory({ projectId }: { projectId: string }) {
  const { executions, loading, error, refresh } = useExecutionHistory(projectId);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const { execution, loading: detailLoading } = useExecution(selectedId);

  if (error) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <ErrorState message={error} onRetry={refresh} />
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-1">
      <div className="w-72 shrink-0 overflow-y-auto border-r border-border-subtle">
        {loading ? (
          <div className="flex flex-col gap-2 p-3">
            <Skeleton className="h-14" />
            <Skeleton className="h-14" />
            <Skeleton className="h-14" />
          </div>
        ) : executions.length === 0 ? (
          <EmptyState
            title="No executions yet."
            description="Executions appear here once you send a message in a conversation."
          />
        ) : (
          <ul className="flex flex-col gap-1 p-2">
            {executions.map((execution) => (
              <li key={execution.id}>
                <button
                  onClick={() => setSelectedId(execution.id)}
                  className={`w-full rounded-md border px-2 py-2 text-left transition-colors ${
                    execution.id === selectedId
                      ? "border-accent/40 bg-accent/10"
                      : "border-transparent hover:bg-panel-alt"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <ExecutionStatusBadge status={execution.status} />
                    <span className="text-[11px] text-faint">
                      {formatRelativeTime(execution.started_at)}
                    </span>
                  </div>
                  <p className="mt-1 line-clamp-2 text-xs text-text">
                    {execution.user_request}
                  </p>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="min-w-0 flex-1 overflow-y-auto p-4">
        {!selectedId && (
          <EmptyState
            title="Select an execution"
            description="Choose an execution from the list to inspect its plan, tool calls, code changes, and test results."
          />
        )}
        {selectedId && detailLoading && !execution && <LoadingRow label="Loading execution…" />}
        {execution && <ExecutionDetails execution={execution} />}
      </div>
    </div>
  );
}
