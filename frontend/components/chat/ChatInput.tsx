"use client";

import { useState } from "react";
import { Spinner } from "@/components/ui/Loading";

export default function ChatInput({
  onSend,
  disabled,
  sending,
}: {
  onSend: (content: string) => void;
  disabled?: boolean;
  sending?: boolean;
}) {
  const [value, setValue] = useState("");

  function submit() {
    const trimmed = value.trim();
    if (!trimmed || disabled || sending) return;
    onSend(trimmed);
    setValue("");
  }

  return (
    <div className="border-t border-border bg-panel p-3">
      <div className="flex items-end gap-2 rounded-lg border border-border bg-panel-alt px-3 py-2 focus-within:border-accent">
        <textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
          disabled={disabled}
          rows={1}
          placeholder={
            disabled ? "Select a conversation to start chatting…" : "Ask the coding agent…"
          }
          className="max-h-40 flex-1 resize-none bg-transparent text-sm text-text placeholder:text-faint focus:outline-none disabled:cursor-not-allowed"
        />
        <button
          onClick={submit}
          disabled={disabled || sending || !value.trim()}
          aria-label="Send message"
          className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-accent text-white transition-colors hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-40"
        >
          {sending ? <Spinner size={14} /> : "↑"}
        </button>
      </div>
      <p className="mt-1 px-1 text-[11px] text-faint">
        Enter to send · Shift + Enter for a new line
      </p>
    </div>
  );
}
