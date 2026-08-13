import { useEffect, useRef } from "react";
import type { Message } from "@/lib/types";
import MessageBubble from "./MessageBubble";
import { Skeleton, Spinner } from "@/components/ui/Loading";
import EmptyState from "@/components/ui/EmptyState";
import ErrorState from "@/components/ui/ErrorState";

export default function MessageList({
  messages,
  loading,
  error,
  onRetry,
  sending,
  lastExecutionId,
  onViewExecution,
}: {
  messages: Message[];
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  sending: boolean;
  lastExecutionId: string | null;
  onViewExecution: (executionId: string) => void;
}) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [messages.length, sending]);

  if (error) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <ErrorState message={error} onRetry={onRetry} />
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex flex-col gap-3 p-4">
        <Skeleton className="h-16" />
        <Skeleton className="h-16" />
      </div>
    );
  }

  if (messages.length === 0 && !sending) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <EmptyState
          title="No messages yet."
          description="Send a coding request to get started."
        />
      </div>
    );
  }

  const lastMessage = messages[messages.length - 1];

  return (
    <div className="flex-1 overflow-y-auto">
      {messages.map((message) => (
        <MessageBubble
          key={message.id}
          message={message}
          executionId={
            message.id === lastMessage?.id && message.role === "assistant"
              ? (lastExecutionId ?? undefined)
              : undefined
          }
          onViewExecution={onViewExecution}
        />
      ))}
      {sending && (
        <div className="flex items-center gap-2 px-4 py-4 text-sm text-muted">
          <Spinner size={14} />
          Agent is working…
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  );
}
