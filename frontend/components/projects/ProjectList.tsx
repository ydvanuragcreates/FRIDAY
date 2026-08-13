import type { Project } from "@/lib/types";
import ProjectCard from "./ProjectCard";
import { Skeleton } from "@/components/ui/Loading";
import EmptyState from "@/components/ui/EmptyState";
import ErrorState from "@/components/ui/ErrorState";
import Button from "@/components/ui/Button";

export default function ProjectList({
  projects,
  loading,
  error,
  onRetry,
  onCreateClick,
}: {
  projects: Project[];
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  onCreateClick: () => void;
}) {
  if (error) {
    return <ErrorState message={error} onRetry={onRetry} />;
  }

  if (loading) {
    return (
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-32" />
        ))}
      </div>
    );
  }

  if (projects.length === 0) {
    return (
      <EmptyState
        title="No projects yet."
        description="Create your first project and start coding with the AI agent."
        action={
          <Button variant="primary" onClick={onCreateClick}>
            + Create Project
          </Button>
        }
      />
    );
  }

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {projects.map((project) => (
        <ProjectCard key={project.id} project={project} />
      ))}
    </div>
  );
}
