"use client";
import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/Dialog";
import { useToast } from "@/components/ui/Toast";
import { api } from "@/lib/api";
import { useProfiles } from "@/lib/profile";

export function DangerZone({ id }: { id: string }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const toast = useToast();
  const router = useRouter();
  const client = useQueryClient();
  const { refresh } = useProfiles();

  async function remove() {
    setBusy(true);
    try {
      await api.del(`/api/profiles/${id}?confirm=true`);
      client.removeQueries({ queryKey: ["profile", id] });
      refresh();
      toast("good", "Preparation profile deleted.");
      setOpen(false);
      router.push("/");
    } catch (error) {
      toast("bad", error instanceof Error ? error.message : "Could not delete.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="border-red-200">
      <h2 className="font-semibold text-ink">Delete this preparation profile</h2>
      <p className="mt-1 max-w-xl text-sm text-muted">Deletes the profile and all of its local lessons, practice attempts, progress and cache entries. Downloaded exports and anything already sent to Groq are outside local deletion.</p>
      <Button variant="danger" className="mt-4" onClick={() => setOpen(true)}>Delete profile…</Button>
      <ConfirmDialog open={open} onClose={() => setOpen(false)} onConfirm={remove} busy={busy} title="Permanently delete this profile?" text="This cannot be undone. All local data for this profile will be removed." confirmLabel="Delete profile" />
    </Card>
  );
}
