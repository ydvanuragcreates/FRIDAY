import type { Message } from "@/lib/types";
import { formatRelativeTime } from "@/lib/format";

export default function MessageBubble({
  message,
  executionId,
  onViewExecution,
}: {
  message: Message;
  executionId?: string;
  onViewExecution?: (executionId: string) => void;
}) {
  const isUser = message.role === "user";

  return (
    <div className="border-b border-border-subtle px-4 py-4 last:border-0">
      <div className="mb-1 flex items-baseline gap-2">
        <span className={`text-xs font-semibold ${isUser ? "text-text" : "text-accent"}`}>
          {isUser ? "You" : "AI Coding Agent"}
        </span>
        <span className="text-[11px] text-faint">
          {formatRelativeTime(message.created_at)}
        </span>
      </div>
      <p className="whitespace-pre-wrap text-sm leading-relaxed text-text">
        {message.content}
      </p>
      {!isUser && executionId && onViewExecution && (
        <button
          onClick={() => onViewExecution(executionId)}
          className="mt-2 text-xs font-medium text-accent hover:text-accent-hover"
        >
          View execution ⟩
        </button>
      )}
    </div>
  );
}
