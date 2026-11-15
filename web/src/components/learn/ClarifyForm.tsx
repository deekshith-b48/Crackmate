"use client";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field, Textarea } from "@/components/ui/Field";
import { useToast } from "@/components/ui/Toast";
import { api } from "@/lib/api";
import { useFormLabels } from "@/lib/queries";
import type { Project, ProfileRecord } from "@/lib/types";

/** Optional answers that make lessons truthful and specific. Saved details are sent to Groq with project lessons. */
export function ClarifyForm({ pid, record, project, onDone }: { pid: string; record: ProfileRecord; project: Project; onDone: () => void }) {
  const labels = useFormLabels().data?.clarifications ?? {};
  const [answers, setAnswers] = useState<Record<string, string>>(project.clarification);
  const [reference, setReference] = useState(project.reference);
  const [busy, setBusy] = useState(false);
  const toast = useToast();
  const client = useQueryClient();

  async function save() {
    setBusy(true);
    try {
      const updated = await api.put<ProfileRecord>(`/api/profiles/${pid}/projects/${project.id}/clarification`, { revision: record.revision, answers, reference });
      client.setQueryData(["profile", pid], updated);
      client.invalidateQueries({ queryKey: ["lesson", pid] });
      client.invalidateQueries({ queryKey: ["overview", pid] });
      toast("good", "Clarification saved. Affected lessons will show as outdated.");
      onDone();
    } catch (error) {
      toast("bad", error instanceof Error ? error.message : "Could not save.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="space-y-4">
      <p className="text-sm text-muted">Add details you can confirm, and skip what you do not know. Remove credentials and private information from snippets. Saved details are sent to Groq when lessons are generated.</p>
      <div className="grid gap-4 sm:grid-cols-2">
        {Object.entries(labels).map(([key, label]) => (
          <Field key={key} label={label} htmlFor={`c-${key}`}><Textarea id={`c-${key}`} maxLength={500} className="min-h-20" value={answers[key] ?? ""} onChange={(e) => setAnswers({ ...answers, [key]: e.target.value })} /></Field>
        ))}
      </div>
      <Field label="README or selected code (optional)" htmlFor="c-ref"><Textarea id="c-ref" maxLength={3500} className="font-mono text-[13px]" value={reference} onChange={(e) => setReference(e.target.value)} /></Field>
      <div className="flex justify-end"><Button variant="primary" onClick={save} loading={busy}>Save clarification</Button></div>
    </Card>
  );
}
