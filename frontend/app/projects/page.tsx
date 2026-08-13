"use client";

import { useState } from "react";
import Header from "@/components/layout/Header";
import ProjectList from "@/components/projects/ProjectList";
import CreateProjectModal from "@/components/projects/CreateProjectModal";
import Button from "@/components/ui/Button";
import { useProjects } from "@/hooks/useProjects";

// This page is a Client Component ('use client') rather than a Server
// Component with a client child, unlike the project workspace route
// below it — the whole page is interactive (create modal, live refresh
// after create/delete) with no meaningfully static part to render on the
// server, so splitting it into a server shell + client body would add a
// file without buying anything. See app/projects/[projectId]/page.tsx
// for a route where that split IS worth it.
export default function ProjectsPage() {
  const { projects, loading, error, refresh, create } = useProjects();
  const [modalOpen, setModalOpen] = useState(false);

  return (
    <div className="flex h-full flex-col">
      <Header />
      <main className="mx-auto w-full max-w-5xl flex-1 overflow-y-auto p-6">
        <div className="mb-4 flex items-center justify-between">
          <h1 className="text-sm font-semibold text-text">Projects</h1>
          <Button variant="primary" onClick={() => setModalOpen(true)}>
            + New Project
          </Button>
        </div>

        <ProjectList
          projects={projects}
          loading={loading}
          error={error}
          onRetry={refresh}
          onCreateClick={() => setModalOpen(true)}
        />
      </main>

      <CreateProjectModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onCreate={create}
      />
    </div>
  );
}
