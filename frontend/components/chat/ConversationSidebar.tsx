import Sidebar, { type SidebarItem } from "@/components/layout/Sidebar";
import type { Conversation } from "@/lib/types";
import { formatRelativeTime } from "@/lib/format";

export default function ConversationSidebar({
  conversations,
  loading,
  selectedId,
  onSelect,
  onCreate,
}: {
  conversations: Conversation[];
  loading: boolean;
  selectedId: string | null;
  onSelect: (id: string) => void;
  onCreate: () => void;
}) {
  const items: SidebarItem[] = conversations.map((c) => ({
    id: c.id,
    label: c.title,
    meta: formatRelativeTime(c.updated_at),
  }));

  return (
    <Sidebar
      title="Conversations"
      items={items}
      selectedId={selectedId}
      onSelect={onSelect}
      onCreateNew={onCreate}
      createLabel="New Conversation"
      loading={loading}
      emptyTitle="No conversations yet."
      emptyDescription="Start a conversation with your coding agent."
    />
  );
}
