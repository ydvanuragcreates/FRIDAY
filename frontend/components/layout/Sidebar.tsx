import { Skeleton } from "@/components/ui/Loading";
import EmptyState from "@/components/ui/EmptyState";

export interface SidebarItem {
  id: string;
  label: string;
  meta?: string;
}

/** Generic compact nav list — used for the conversation list inside a
 * project workspace (see components/chat/ConversationSidebar.tsx). The
 * richer project picker on /projects uses card components instead
 * (components/projects/ProjectList.tsx) since it needs to show more per
 * item (description, repo path, conversation count) than a nav list fits.
 */
export default function Sidebar({
  title,
  items,
  selectedId,
  onSelect,
  onCreateNew,
  createLabel,
  loading,
  emptyTitle,
  emptyDescription,
}: {
  title: string;
  items: SidebarItem[];
  selectedId?: string | null;
  onSelect: (id: string) => void;
  onCreateNew?: () => void;
  createLabel?: string;
  loading?: boolean;
  emptyTitle?: string;
  emptyDescription?: string;
}) {
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-border px-3 py-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-muted">
          {title}
        </span>
      </div>

      {onCreateNew && (
        <div className="border-b border-border-subtle p-2">
          <button
            onClick={onCreateNew}
            className="w-full rounded-md border border-dashed border-border px-2 py-1.5 text-left text-sm text-muted hover:border-accent hover:text-accent"
          >
            + {createLabel ?? "New"}
          </button>
        </div>
      )}

      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="flex flex-col gap-2 p-3">
            <Skeleton className="h-9" />
            <Skeleton className="h-9" />
            <Skeleton className="h-9" />
          </div>
        ) : items.length === 0 ? (
          <EmptyState
            title={emptyTitle ?? "Nothing here yet"}
            description={emptyDescription}
          />
        ) : (
          <ul className="flex flex-col gap-0.5 p-2">
            {items.map((item) => (
              <li key={item.id}>
                <button
                  onClick={() => onSelect(item.id)}
                  className={`w-full truncate rounded-md px-2 py-1.5 text-left text-sm transition-colors ${
                    item.id === selectedId
                      ? "bg-accent/15 text-accent"
                      : "text-text hover:bg-panel-alt"
                  }`}
                >
                  <div className="truncate">{item.label}</div>
                  {item.meta && (
                    <div className="truncate text-xs text-faint">{item.meta}</div>
                  )}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
