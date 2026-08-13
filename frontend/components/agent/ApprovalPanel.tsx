"use client";

import { useEffect, useState } from "react";
import { ApiError, getTask, submitTaskDecision } from "@/lib/api";
import type { TaskResponse } from "@/lib/types";
import Button from "@/components/ui/Button";
import { LoadingRow } from "@/components/ui/Loading";
import DiffView from "./DiffView";

/**
 * The diffs shown here come from `GET /api/tasks/{executionId}`, NOT
 * `GET /api/executions/{id}` — while an execution is `waiting_for_approval`,
 * `code_changes` on the execution record is still empty (apply_changes_node
 * hasn't run yet), so the pending proposal only exists at the Phase 5
 * "task" endpoint. `execution_id` doubles as that endpoint's `thread_id` —
 * see README, Phase 7 > "How LangGraph talks to the database".
 */
export default function ApprovalPanel({
  executionId,
  onDecided,
}: {
  executionId: string;
  onDecided: () => void;
}) {
  const [task, setTask] = useState<TaskResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [decideError, setDecideError] = useState<string | null>(null);
  const [deciding, setDeciding] = useState<"approve" | "reject" | null>(null);
  const [expandedFile, setExpandedFile] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    // Fetch-on-mount for the given executionId — see hooks/useProjects.ts
    // for the fuller note on why this shape is intentional here.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    setLoadError(null);
    getTask(executionId)
      .then((t) => {
        if (!cancelled) setTask(t);
      })
      .catch((err) => {
        if (!cancelled) {
          setLoadError(
            err instanceof ApiError ? err.message : "Failed to load proposed changes.",
          );
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [executionId]);

  async function decide(approved: boolean) {
    setDeciding(approved ? "approve" : "reject");
    setDecideError(null);
    try {
      await submitTaskDecision(executionId, approved);
      onDecided();
    } catch (err) {
      setDecideError(
        err instanceof ApiError ? err.message : "Failed to submit decision.",
      );
    } finally {
      setDeciding(null);
    }
  }

  if (loading) return <LoadingRow label="Loading proposed changes…" />;
  if (loadError) return <p className="px-3 py-2 text-xs text-danger">{loadError}</p>;
  if (!task) return null;

  const fileCount = task.proposed_changes.length;

  return (
    <div className="rounded-md border border-warning/30 bg-warning/5 p-3">
      <p className="text-xs font-semibold text-text">
        Agent wants to modify {fileCount} file{fileCount === 1 ? "" : "s"}
      </p>

      <ul className="mt-2 flex flex-col gap-1">
        {task.proposed_changes.map((change) => (
          <li key={change.file_path}>
            <button
              onClick={() =>
                setExpandedFile((f) => (f === change.file_path ? null : change.file_path))
              }
              className="w-full truncate rounded bg-panel-alt px-2 py-1 text-left font-mono text-[11px] text-muted hover:text-text"
            >
              {change.file_path}
            </button>
            {expandedFile === change.file_path && (
              <div className="mt-1">
                <DiffView diff={change.diff} />
              </div>
            )}
          </li>
        ))}
      </ul>

      {decideError && <p className="mt-2 text-xs text-danger">{decideError}</p>}

      <div className="mt-3 flex gap-2">
        <Button
          variant="danger"
          onClick={() => decide(false)}
          loading={deciding === "reject"}
          disabled={deciding !== null}
        >
          Reject
        </Button>
        <Button
          variant="primary"
          onClick={() => decide(true)}
          loading={deciding === "approve"}
          disabled={deciding !== null}
        >
          Approve
        </Button>
      </div>
    </div>
  );
}
