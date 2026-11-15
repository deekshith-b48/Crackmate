"use client";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field, Input, Textarea } from "@/components/ui/Field";
import { TagInput } from "@/components/ui/TagInput";
import { useToast } from "@/components/ui/Toast";
import { api } from "@/lib/api";
import { useProfiles } from "@/lib/profile";
import { useFormLabels } from "@/lib/queries";
import type { ProfileRecord } from "@/lib/types";

export function ProfileForm({ record }: { record: ProfileRecord }) {
  const { profile } = record;
  const labels = useFormLabels().data?.skill_labels ?? {};
  const toast = useToast();
  const client = useQueryClient();
  const { refresh } = useProfiles();
  const [saving, setSaving] = useState(false);
  const [f, setF] = useState({
    name: profile.name ?? "", experience_level: profile.experience_level ?? "", summary: profile.summary ?? "",
    work: profile.work_experience.join("\n"), education: profile.education.join("\n"),
    role: profile.role ?? "", company: profile.company ?? "", job_description: profile.job_description ?? "",
    skills: profile.skills,
  });
  const set = (patch: Partial<typeof f>) => setF((old) => ({ ...old, ...patch }));

  async function save() {
    setSaving(true);
    try {
      const updated = await api.put<ProfileRecord>(`/api/profiles/${record.id}`, {
        revision: record.revision, name: f.name, experience_level: f.experience_level, summary: f.summary, skills: f.skills,
        work_experience: f.work.split("\n"), education: f.education.split("\n"),
        role: f.role, company: f.company, job_description: f.job_description,
      });
      client.setQueryData(["profile", record.id], updated);
      refresh();
      toast("good", "Profile changes saved.");
    } catch (error) {
      toast("bad", error instanceof Error ? error.message : "Could not save.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      <Card className="space-y-4">
        <h2 className="font-semibold text-ink">About you</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Name" htmlFor="name" hint="Optional. Used only to greet you."><Input id="name" maxLength={200} value={f.name} onChange={(e) => set({ name: e.target.value })} /></Field>
          <Field label="Experience level" htmlFor="level"><Input id="level" maxLength={200} value={f.experience_level} onChange={(e) => set({ experience_level: e.target.value })} placeholder="Fresher, 2 years…" /></Field>
        </div>
        <Field label="Summary" htmlFor="summary"><Textarea id="summary" maxLength={8000} value={f.summary} onChange={(e) => set({ summary: e.target.value })} /></Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Work experience" htmlFor="work" hint="One entry per line."><Textarea id="work" value={f.work} onChange={(e) => set({ work: e.target.value })} /></Field>
          <Field label="Education" htmlFor="edu" hint="One entry per line."><Textarea id="edu" value={f.education} onChange={(e) => set({ education: e.target.value })} /></Field>
        </div>
      </Card>

      <Card className="space-y-4">
        <h2 className="font-semibold text-ink">Skills</h2>
        <p className="-mt-2 text-sm text-muted">Type a skill and press Enter. Your skills become topics to study.</p>
        <div className="grid gap-4 sm:grid-cols-2">
          {Object.entries(labels).map(([key, label]) => (
            <Field key={key} label={label} htmlFor={`skill-${key}`}>
              <TagInput id={`skill-${key}`} value={f.skills[key] ?? []} onChange={(tags) => set({ skills: { ...f.skills, [key]: tags } })} placeholder="Add a skill" />
            </Field>
          ))}
        </div>
      </Card>

      <Card className="space-y-4">
        <h2 className="font-semibold text-ink">Interview target</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Target role" htmlFor="t-role"><Input id="t-role" maxLength={200} value={f.role} onChange={(e) => set({ role: e.target.value })} /></Field>
          <Field label="Company" htmlFor="t-company"><Input id="t-company" maxLength={200} value={f.company} onChange={(e) => set({ company: e.target.value })} /></Field>
        </div>
        <Field label="Job description" htmlFor="t-jd"><Textarea id="t-jd" maxLength={8000} value={f.job_description} onChange={(e) => set({ job_description: e.target.value })} /></Field>
      </Card>

      <div className="sticky bottom-4 flex justify-end"><Button variant="primary" onClick={save} loading={saving}>Save profile details</Button></div>
    </div>
  );
}
