"use client";

import { useState } from "react";
import Drawer from "@/components/ui/Drawer";

/**
 * The three-column project workspace (see README, Phase 8 "Layout"):
 * conversations | chat | agent activity. Responsive per the spec:
 *  - Agent panel is a persistent column only at `lg` and up; a drawer
 *    below that (so it's a drawer on both tablet and mobile).
 *  - Conversations is a persistent column at `md` and up; a drawer
 *    below that (mobile only).
 * Chat is always the primary, always-visible content.
 */
export default function WorkspaceLayout({
  conversations,
  chat,
  agentPanel,
}: {
  conversations: React.ReactNode;
  chat: React.ReactNode;
  agentPanel: React.ReactNode;
}) {
  const [showConversations, setShowConversations] = useState(false);
  const [showAgentPanel, setShowAgentPanel] = useState(false);

  return (
    <div className="flex flex-1 overflow-hidden">
      <div className="hidden w-64 shrink-0 border-r border-border md:block">
        {conversations}
      </div>

      <div className="flex min-w-0 flex-1 flex-col">
        {/* The row itself has to stay visible through the whole range
            where AT LEAST ONE trigger is needed (i.e. up to `lg`) — it
            can't be `md:hidden`, or the Activity trigger disappears
            along with it at the `md` breakpoint even though it's still
            needed on tablet. Each button hides itself independently. */}
        <div className="flex items-center gap-3 border-b border-border-subtle px-3 py-1.5 lg:hidden">
          <button
            onClick={() => setShowConversations(true)}
            className="text-xs font-medium text-muted hover:text-text md:hidden"
          >
            ☰ Conversations
          </button>
          <button
            onClick={() => setShowAgentPanel(true)}
            className="ml-auto text-xs font-medium text-muted hover:text-text"
          >
            Activity ⟩
          </button>
        </div>
        {chat}
      </div>

      <div className="hidden w-80 shrink-0 border-l border-border lg:block">
        {agentPanel}
      </div>

      {showConversations && (
        <div className="md:hidden">
          <Drawer side="left" onClose={() => setShowConversations(false)}>
            {conversations}
          </Drawer>
        </div>
      )}
      {showAgentPanel && (
        <div className="lg:hidden">
          <Drawer side="right" onClose={() => setShowAgentPanel(false)}>
            {agentPanel}
          </Drawer>
        </div>
      )}
    </div>
  );
}
