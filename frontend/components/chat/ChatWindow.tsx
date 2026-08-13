import type { Message } from "@/lib/types";
import MessageList from "./MessageList";
import ChatInput from "./ChatInput";
import EmptyState from "@/components/ui/EmptyState";

export default function ChatWindow({
  conversationSelected,
  messages,
  loading,
  error,
  onRetry,
  sending,
  sendError,
  activeExecutionId,
  onSend,
  onViewExecution,
}: {
  conversationSelected: boolean;
  messages: Message[];
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  sending: boolean;
  sendError: string | null;
  activeExecutionId: string | null;
  onSend: (content: string) => void;
  onViewExecution: (executionId: string) => void;
}) {
  if (!conversationSelected) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <EmptyState
          title="No conversation selected."
          description="Pick a conversation from the left, or start a new one."
        />
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <MessageList
        messages={messages}
        loading={loading}
        error={error}
        onRetry={onRetry}
        sending={sending}
        lastExecutionId={activeExecutionId}
        onViewExecution={onViewExecution}
      />
      {sendError && (
        <p className="border-t border-danger/30 bg-danger/10 px-4 py-2 text-xs text-danger">
          {sendError}
        </p>
      )}
      <ChatInput onSend={onSend} sending={sending} />
    </div>
  );
}
