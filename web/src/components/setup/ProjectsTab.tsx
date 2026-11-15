"use client";
import { useQueryClient } from "@tanstack/react-query";
import { FolderPlus, Pencil, Trash2, Workflow } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ConfirmDialog, Dialog } from "@/components/ui/Dialog";
import { EmptyState } from "@/components/ui/EmptyState";
import { Field, Input, Textarea } from "@/components/ui/Field";
import { TagInput } from "@/components/ui/TagInput";
import { useToast } from "@/components/ui/Toast";
import { api } from "@/lib/api";
import { useProfiles } from "@/lib/profile";
import type { Project, ProfileRecord } from "@/lib/types";

const EMPTY = { title: "", summary: "", technologies: [] as string[], contribution: "", implementation: "" };

export function ProjectsTab({ record }: { record: ProfileRecord }) {
  const toast = useToast();
  const client = useQueryClient();
  const { refresh } = useProfiles();
  const [editing, setEditing] = useState<Project | "new" | null>(null);
  const [removing, setRemoving] = useState<Project | null>(null);
  const [form, setForm] = useState(EMPTY);
  const [busy, setBusy] = useState(false);
  const projects = record.profile.projects;

  const open = (target: Project | "new") => {
    setForm(target === "new" ? EMPTY : { title: target.title, summary: target.summary, technologies: target.technologies, contribution: target.contribution, implementation: target.implementation });
    setEditing(target);
  };

  async function run(action: () => Promise<ProfileRecord>, message: string) {
    setBusy(true);
    try {
      client.setQueryData(["profile", record.id], await action());
      refresh();
      toast("good", message);
      setEditing(null);
      setRemoving(null);
    } catch (error) {
      toast("bad", error instanceof Error ? error.message : "Could not save.");
    } finally {
      setBusy(false);
    }
  }

  const base = `/api/profiles/${record.id}/projects`;
  const save = () => run(() => editing === "new"
    ? api.post<ProfileRecord>(base, { revision: record.revision, ...form })
    : api.put<ProfileRecord>(`${base}/${(editing as Project).id}`, { revision: record.revision, ...form }), "Project saved.");

  if (!projects.length && !editing) {
    return <EmptyState icon={Workflow} title="Add your first project" text="Projects are where interviews go deep. Add one and CrackMate will teach the concepts behind it." action={<Button variant="primary" onClick={() => open("new")}><FolderPlus className="size-4" /> Add a project</Button>} />;
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-end"><Button variant="primary" onClick={() => open("new")}><FolderPlus className="size-4" /> Add a project</Button></div>
      {projects.map((project) => (
        <Card key={project.id} className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <h3 className="font-semibold text-ink">{project.title}</h3>
            {project.summary && <p className="mt-1 line-clamp-2 text-sm text-muted">{project.summary}</p>}
            <div className="mt-3 flex flex-wrap gap-1.5">{project.technologies.map((t) => <Badge key={t} tone="brand">{t}</Badge>)}</div>
            {!project.contribution && <p className="mt-3 text-xs text-warn">Add what you personally built so lessons stay truthful.</p>}
          </div>
          <div className="flex shrink-0 gap-1">
            <Button variant="ghost" size="sm" onClick={() => open(project)} aria-label={`Edit ${project.title}`}><Pencil className="size-4" /></Button>
            <Button variant="ghost" size="sm" onClick={() => setRemoving(project)} aria-label={`Remove ${project.title}`}><Trash2 className="size-4" /></Button>
          </div>
        </Card>
      ))}

      <Dialog open={editing !== null} onClose={() => setEditing(null)} title={editing === "new" ? "Add a project" : "Edit project"} wide>
        <div className="space-y-4">
          <Field label="Project title" htmlFor="p-title"><Input id="p-title" maxLength={200} value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></Field>
          <Field label="Summary" htmlFor="p-summary"><Textarea id="p-summary" maxLength={2400} value={form.summary} onChange={(e) => setForm({ ...form, summary: e.target.value })} /></Field>
          <Field label="Technologies" htmlFor="p-tech"><TagInput id="p-tech" value={form.technologies} onChange={(technologies) => setForm({ ...form, technologies })} placeholder="React, Node.js…" /></Field>
          <Field label="Your contribution" htmlFor="p-contrib" hint="What did you personally implement? Be specific and truthful."><Textarea id="p-contrib" maxLength={2400} value={form.contribution} onChange={(e) => setForm({ ...form, contribution: e.target.value })} /></Field>
          <Field label="Known implementation details" htmlFor="p-impl"><Textarea id="p-impl" maxLength={3500} value={form.implementation} onChange={(e) => setForm({ ...form, implementation: e.target.value })} /></Field>
          <div className="flex justify-end gap-2"><Button variant="ghost" onClick={() => setEditing(null)}>Cancel</Button><Button variant="primary" onClick={save} loading={busy} disabled={!form.title.trim()}>Save project</Button></div>
        </div>
      </Dialog>
      <ConfirmDialog open={!!removing} onClose={() => setRemoving(null)} busy={busy} title="Remove this project?" text={`“${removing?.title}” and its clarification notes will be removed from your profile. Saved lessons for it will no longer appear.`} confirmLabel="Remove project"
        onConfirm={() => run(() => api.del<ProfileRecord>(`${base}/${removing!.id}?revision=${record.revision}`), "Project removed.")} />
    </div>
  );
}
