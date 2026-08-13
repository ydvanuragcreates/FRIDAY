"use client";

import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  getExecutions,
  getMessages,
  sendMessage as apiSendMessage,
} from "@/lib/api";
import type { Message, SendMessageResponse } from "@/lib/types";

const DISCOVERY_POLL_MS = 800;
const ACTIVE_EXECUTION_STATUSES = new Set(["pending", "running"]);

/** `conversationId` is nullable so this hook can be called unconditionally
 * from ProjectWorkspace even before a conversation is selected — React
 * hooks can't be called conditionally, so the alternative would be a
 * second component just to delay mounting this hook, for no real benefit.
 */
export function useMessages(projectId: string, conversationId: string | null) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);

  // The execution the Agent Activity panel should be watching right now.
  // Two ways it gets set: (1) discovered while a send is still in flight
  // (see below — best-effort, since POST /messages doesn't return an id
  // until it's done), or (2) the authoritative id once that POST resolves.
  const [activeExecutionId, setActiveExecutionId] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!conversationId) return;
    setLoading(true);
    setError(null);
    try {
      setMessages(await getMessages(conversationId));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load messages.");
    } finally {
      setLoading(false);
    }
  }, [conversationId]);

  useEffect(() => {
    // Resetting state when `conversationId` changes, then re-fetching for
    // the new one — see hooks/useProjects.ts for why this "fetch on
    // mount/on prop change" shape is intentional here.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setActiveExecutionId(null);
    if (!conversationId) {
      setMessages([]);
      return;
    }
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversationId]);

  const send = useCallback(
    async (content: string): Promise<SendMessageResponse> => {
      if (!conversationId) throw new Error("No conversation selected.");
      setSending(true);
      setSendError(null);
      setActiveExecutionId(null);

      // Optimistic: the user sees their own message the instant they hit
      // send, not after a full agent run completes.
      const optimisticId = `optimistic-${Date.now()}`;
      const optimisticMessage: Message = {
        id: optimisticId,
        conversation_id: conversationId,
        role: "user",
        content,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, optimisticMessage]);

      // Best-effort discovery loop: while we wait for the blocking POST
      // below, poll the project's execution list for the row it just
      // created (visible as soon as ConversationService commits it — see
      // README, Phase 7's "Transactions" section) so the Agent Activity
      // panel has something to watch from the very start of the run,
      // not just after the whole thing finishes.
      let discovering = true;
      const discover = async () => {
        while (discovering) {
          try {
            const executions = await getExecutions(projectId);
            const candidate = executions.find(
              (e) =>
                e.conversation_id === conversationId &&
                ACTIVE_EXECUTION_STATUSES.has(e.status),
            );
            if (candidate) {
              setActiveExecutionId((current) => current ?? candidate.id);
              return;
            }
          } catch {
            // transient — the send() call below will surface a real error
            // if the backend is actually unreachable
          }
          await new Promise((resolve) => setTimeout(resolve, DISCOVERY_POLL_MS));
        }
      };
      discover();

      try {
        const result = await apiSendMessage(conversationId, content);
        discovering = false;
        setActiveExecutionId(result.execution_id); // authoritative — overrides any guess

        setMessages((prev) => {
          const withoutOptimistic = prev.filter((m) => m.id !== optimisticId);
          const next = [...withoutOptimistic, result.user_message];
          if (result.assistant_message) next.push(result.assistant_message);
          return next;
        });

        return result;
      } catch (err) {
        discovering = false;
        setMessages((prev) => prev.filter((m) => m.id !== optimisticId));
        const message =
          err instanceof ApiError ? err.message : "Failed to send message.";
        setSendError(message);
        throw err;
      } finally {
        setSending(false);
      }
    },
    [projectId, conversationId],
  );

  return {
    messages,
    loading,
    error,
    sending,
    sendError,
    activeExecutionId,
    refresh,
    send,
  };
}
