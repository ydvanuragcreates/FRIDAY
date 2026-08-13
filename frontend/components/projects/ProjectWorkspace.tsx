"use client";

import { useEffect, useState } from "react";
import Header from "@/components/layout/Header";
import WorkspaceLayout from "@/components/layout/WorkspaceLayout";
import ProjectOverview from "./ProjectOverview";
import ConversationSidebar from "@/components/chat/ConversationSidebar";
import ChatWindow from "@/components/chat/ChatWindow";
import AgentActivity from "@/components/agent/AgentActivity";
import ExecutionHistory from "@/components/agent/ExecutionHistory";
import { useConversations } from "@/hooks/useConversations";
import { useMessages } from "@/hooks/useMessages";
import { useExecutionHistory } from "@/hooks/useExecution";
import type { Project } from "@/lib/types";

type Tab = "chat" | "history";

export default function ProjectWorkspace({
  projectId,
  initialProject,
}: {
  projectId: string;
  initialProject: Project;
}) {
  const [tab, setTab] = useState<Tab>("chat");
  const [selectedConversationId, setSelectedConversationId] = useState<string | null>(null);
  // Set by clicking "View execution" on a past message — pins the Agent
  // Activity panel to that run instead of whatever's currently active.
  const [viewingExecutionId, setViewingExecutionId] = useState<string | null>(null);

  const conversations = useConversations(projectId);
  const messages = useMessages(projectId, selectedConversationId);
  const { executions } = useExecutionHistory(projectId);

  useEffect(() => {
    // Reset the pinned "viewing" execution when the conversation changes
    // — see hooks/useProjects.ts for the fuller note on this lint rule.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setViewingExecutionId(null);
  }, [selectedConversationId]);

  async function handleCreateConversation() {
    const conversation = await conversations.create(
      `Conversation ${new Date().toLocaleString()}`,
    );
    setSelectedConversationId(conversation.id);
    setTab("chat");
  }

  async function handleSend(content: string) {
    setViewingExecutionId(null);
    await messages.send(content);
  }

  const panelExecutionId = viewingExecutionId ?? messages.activeExecutionId;

  return (
    <div className="flex h-full flex-col">
      <Header projectName={initialProject.name} />
      <ProjectOverview project={initialProject} lastExecution={executions[0]} />

      <div className="flex items-center gap-1 border-b border-border-subtle bg-panel px-3">
        <TabButton active={tab === "chat"} onClick={() => setTab("chat")}>
          Chat
        </TabButton>
        <TabButton active={tab === "history"} onClick={() => setTab("history")}>
          Execution History
        </TabButton>
      </div>

      {tab === "chat" ? (
        <WorkspaceLayout
          conversations={
            <ConversationSidebar
              conversations={conversations.conversations}
              loading={conversations.loading}
              selectedId={selectedConversationId}
              onSelect={setSelectedConversationId}
              onCreate={handleCreateConversation}
            />
          }
          chat={
            <ChatWindow
              conversationSelected={selectedConversationId !== null}
              messages={messages.messages}
              loading={messages.loading}
              error={messages.error}
              onRetry={messages.refresh}
              sending={messages.sending}
              sendError={messages.sendError}
              activeExecutionId={messages.activeExecutionId}
              onSend={handleSend}
              onViewExecution={setViewingExecutionId}
            />
          }
          agentPanel={<AgentActivity executionId={panelExecutionId} />}
        />
      ) : (
        <ExecutionHistory projectId={projectId} />
      )}
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`border-b-2 px-2 py-2 text-xs font-medium transition-colors ${
        active
          ? "border-accent text-text"
          : "border-transparent text-muted hover:text-text"
      }`}
    >
      {children}
    </button>
  );
}
