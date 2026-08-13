"use client";

import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  createConversation as apiCreateConversation,
  getConversations,
} from "@/lib/api";
import type { Conversation } from "@/lib/types";

export function useConversations(projectId: string) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setConversations(await getConversations(projectId));
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Failed to load conversations.",
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

  const create = useCallback(
    async (title: string) => {
      const conversation = await apiCreateConversation(projectId, title);
      setConversations((prev) => [conversation, ...prev]);
      return conversation;
    },
    [projectId],
  );

  return { conversations, loading, error, refresh, create };
}
