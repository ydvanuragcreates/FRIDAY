"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Modal from "@/components/ui/Modal";
import Button from "@/components/ui/Button";
import { ApiError } from "@/lib/api";
import type { Project, ProjectCreateInput } from "@/lib/types";

export default function CreateProjectModal({
  open,
  onClose,
  onCreate,
}: {
  open: boolean;
  onClose: () => void;
  onCreate: (input: ProjectCreateInput) => Promise<Project>;
}) {
  const router = useRouter();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [repositoryPath, setRepositoryPath] = useState("");
  const [repositoryUrl, setRepositoryUrl] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function reset() {
    setName("");
    setDescription("");
    setRepositoryPath("");
    setRepositoryUrl("");
    setError(null);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const project = await onCreate({
        name,
        description: description || null,
        repository_path: repositoryPath,
        repository_url: repositoryUrl || null,
      });
      reset();
      onClose();
      // Create Project -> project created -> navigate to project workspace
      router.push(`/projects/${project.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create project.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={() => {
        reset();
        onClose();
      }}
      title="New Project"
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-3">
        <Field label="Project Name" required>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            autoFocus
            className={inputClasses}
            placeholder="My FastAPI App"
          />
        </Field>

        <Field label="Description">
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={2}
            className={inputClasses}
            placeholder="Backend project"
          />
        </Field>

        <Field label="Repository Path" required>
          <input
            value={repositoryPath}
            onChange={(e) => setRepositoryPath(e.target.value)}
            required
            className={`${inputClasses} font-mono`}
            placeholder="/workspace/my-fastapi-app"
          />
        </Field>

        <Field label="Repository URL (optional)">
          <input
            value={repositoryUrl}
            onChange={(e) => setRepositoryUrl(e.target.value)}
            className={inputClasses}
            placeholder="https://github.com/you/repo"
          />
        </Field>

        {error && <p className="text-xs text-danger">{error}</p>}

        <div className="mt-2 flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" loading={submitting}>
            Create Project
          </Button>
        </div>
      </form>
    </Modal>
  );
}

const inputClasses =
  "w-full rounded-md border border-border bg-panel-alt px-2.5 py-1.5 text-sm text-text placeholder:text-faint focus:border-accent focus:outline-none";

function Field({
  label,
  required,
  children,
}: {
  label: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-xs font-medium text-muted">
        {label}
        {required && <span className="text-danger"> *</span>}
      </span>
      {children}
    </label>
  );
}
