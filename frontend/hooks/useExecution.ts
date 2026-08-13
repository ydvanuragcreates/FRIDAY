"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError, getExecution, getExecutions } from "@/lib/api";
import type { ExecutionDetail, ExecutionSummary } from "@/lib/types";

const ACTIVE_STATUSES = new Set(["pending", "running", "waiting_for_approval"]);
const POLL_INTERVAL_MS = 1500;

/**
 * Polls `GET /api/executions/{id}` while the execution is in an active
 * status, and stops once it reaches a terminal one (completed/failed/
 * cancelled) — there's nothing left to change after that.
 *
 * This is also how "live" agent activity works at all: the backend has
 * no WebSocket/SSE (POST /messages is one blocking call — see README,
 * Phase 8), but every node commits its own row as the graph runs, so a
 * concurrent poll of this endpoint genuinely observes progress in real
 * time even while that POST is still in flight, once an execution_id is
 * known. See hooks/useMessages.ts for how an id is found *before* the
 * POST resolves.
 */
export function useExecution(executionId: string | null) {
  const [execution, setExecution] = useState<ExecutionDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchOnce = useCallback(async (): Promise<ExecutionDetail | null> => {
    if (!executionId) return null;
    try {
      const detail = await getExecution(executionId);
      setExecution(detail);
      setError(null);
      return detail;
    } catch (err) {
      // A brand-new execution_id can 404 for an instant if this poll
      // lands before the row is committed on the writing connection —
      // treat that as "not ready yet," not a real error, and keep polling.
      if (err instanceof ApiError && err.status === 404) return null;
      setError(err instanceof ApiError ? err.message : "Failed to load execution.");
      return null;
    }
  }, [executionId]);

  useEffect(() => {
    if (!executionId) {
      // Resetting local state when a prop goes away (here: no execution
      // to watch anymore) is a standard effect use — see
      // hooks/useProjects.ts for the fuller note on this lint rule.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setExecution(null);
      setError(null);
      return;
    }

    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    async function poll() {
      const detail = await fetchOnce();
      if (cancelled) return;
      setLoading(false);
      if (detail && !ACTIVE_STATUSES.has(detail.status)) return; // terminal — stop polling
      timer = setTimeout(poll, POLL_INTERVAL_MS);
    }

    setLoading(true);
    poll();

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [executionId, fetchOnce]);

  return { execution, loading, error, refresh: fetchOnce };
}

/** The (non-polling) list side, for "view previous agent executions" —
 * GET /api/projects/{id}/executions, already ordered newest-first by
 * the backend.
 */
export function useExecutionHistory(projectId: string) {
  const [executions, setExecutions] = useState<ExecutionSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setExecutions(await getExecutions(projectId));
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Failed to load execution history.",
      );
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    // See hooks/useProjects.ts for why this "fetch on mount" effect is
    // intentional and the lint rule below is a deliberate, explained opt-out.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refresh();
  }, [refresh]);

  return { executions, loading, error, refresh };
}
