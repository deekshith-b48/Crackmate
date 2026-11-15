"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Library, RefreshCw, Search, Trash2 } from "lucide-react";
import { useRef, useState } from "react";
import { PageHeader } from "@/components/shell/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/Dialog";
import { EmptyState } from "@/components/ui/EmptyState";
import { Field, Input, Textarea } from "@/components/ui/Field";
import { StepGenerating } from "@/components/ui/StepGenerating";
import { Tabs } from "@/components/ui/Tabs";
import { useToast } from "@/components/ui/Toast";
import { api } from "@/lib/api";
import { useJob } from "@/lib/stream";
import type { SearchPassage, Source } from "@/lib/types";

type Mode = "paste" | "url" | "file";

export default function KnowledgeLibrary() {
  const client = useQueryClient();
  const toast = useToast();
  const { data: sources = [] } = useQuery({ queryKey: ["sources"], queryFn: () => api.get<Source[]>("/api/knowledge/sources") });
  const [q, setQ] = useState("");
  const { data: hits = [] } = useQuery({ queryKey: ["search", q], queryFn: () => api.get<SearchPassage[]>(`/api/knowledge/search?q=${encodeURIComponent(q)}`), enabled: q.trim().length > 2 });
  const [filter, setFilter] = useState("");
  const [mode, setMode] = useState<Mode>("paste");
  const [form, setForm] = useState({ title: "", url: "", text: "", license: "Unknown" });
  const [removing, setRemoving] = useState<Source | null>(null);
  const [busy, setBusy] = useState(false);
  const picker = useRef<HTMLInputElement>(null);
  const build = useJob<{ imported: number; unchanged: number }>();
  const refresh = () => client.invalidateQueries({ queryKey: ["sources"] });
  const fail = (e: unknown) => toast("bad", e instanceof Error ? e.message : "That did not work.");

  async function importIt(file?: File) {
    setBusy(true);
    try {
      if (file) { const body = new FormData(); body.append("file", file); body.append("title", form.title); body.append("license", form.license); await api.post("/api/knowledge/import-file", body); }
      else await api.post("/api/knowledge/import", mode === "url" ? { ...form, text: "" } : { ...form, url: "" });
      toast("good", "Source imported."); refresh();
    } catch (e) { fail(e); } finally { setBusy(false); }
  }
  async function buildBase() {
    const out = await build.run("/api/knowledge/build");
    if (out) { refresh(); toast("good", `Imported ${out.imported} sections, ${out.unchanged} unchanged.`); }
  }
  const shown = sources.filter((s) => s.title.toLowerCase().includes(filter.toLowerCase())).slice(0, 60);

  return (
    <>
      <PageHeader title="Knowledge Library" description="Trusted sources behind your lessons. Shared by every profile; deleting a profile leaves these available." />
      <div className="space-y-6">
        <Card className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="font-semibold text-ink">Study knowledge base</h2><p className="max-w-xl text-sm text-muted">Downloads System Design Primer (CC BY 4.0), Tech Interview Handbook (MIT) and Coding Interview University (CC BY-SA 4.0), keeps only their text with links back to the originals, then deletes the downloads (about 70 MB, one time).</p></div><Button variant="primary" onClick={buildBase} loading={build.status === "running"}>Build knowledge base</Button></div>
          {build.status === "running" && <StepGenerating title="Building the knowledge base" steps={build.steps} running startedAt={build.startedAt} />}
          {build.status === "error" && <p role="alert" className="text-sm text-bad">{build.error}</p>}
        </Card>

        <Card className="space-y-4">
          <h2 className="font-semibold text-ink">Import a source</h2>
          <Tabs<Mode> tabs={[{ id: "paste", label: "Paste text" }, { id: "url", label: "Public URL" }, { id: "file", label: "Upload file" }]} value={mode} onChange={setMode} />
          <div className="grid gap-4 sm:grid-cols-2"><Field label="Source title" htmlFor="st"><Input id="st" maxLength={200} value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></Field><Field label="Reuse terms or license" htmlFor="sl" hint="Leave Unknown when uncertain."><Input id="sl" value={form.license} onChange={(e) => setForm({ ...form, license: e.target.value })} /></Field></div>
          {mode === "paste" && <><Field label="Source text" htmlFor="stext"><Textarea id="stext" maxLength={100000} value={form.text} onChange={(e) => setForm({ ...form, text: e.target.value })} className="min-h-32" /></Field><Button variant="primary" onClick={() => importIt()} loading={busy} disabled={!form.text.trim()}>Import source</Button></>}
          {mode === "url" && <><Field label="Public source URL" htmlFor="surl"><Input id="surl" value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} placeholder="https://" /></Field><Button variant="primary" onClick={() => importIt()} loading={busy} disabled={!form.url.trim()}>Import source</Button></>}
          {mode === "file" && <><input ref={picker} type="file" accept=".txt,.md,.pdf" className="sr-only" aria-label="Source file" onChange={(e) => { const f = e.target.files?.[0]; if (f) importIt(f); e.target.value = ""; }} /><Button variant="primary" onClick={() => picker.current?.click()} loading={busy}>Choose a .txt, .md or .pdf file (up to 2 MB)</Button></>}
        </Card>

        <div>
          <div className="relative"><Search className="absolute left-3 top-3 size-4 text-muted" aria-hidden /><Input aria-label="Search saved passages" placeholder="Search saved passages, for example load balancer" value={q} onChange={(e) => setQ(e.target.value)} className="pl-9" /></div>
          {hits.length > 0 && <div className="mt-3 space-y-2">{hits.map((h) => <details key={h.id} className="rounded-[var(--radius-control)] border border-line bg-surface px-3 py-2 text-sm"><summary className="cursor-pointer font-medium text-ink">{h.title} · {h.heading}</summary><p className="mt-2 whitespace-pre-wrap">{h.text}</p><p className="mt-2 break-all text-xs text-muted">{h.location}{h.license ? ` · ${h.license}` : ""}</p></details>)}</div>}
        </div>

        <section>
          <div className="mb-3 flex items-center justify-between gap-3"><h2 className="font-semibold text-ink">{sources.length} saved sources</h2><Input aria-label="Filter sources" placeholder="Filter by title" value={filter} onChange={(e) => setFilter(e.target.value)} className="max-w-64" /></div>
          {sources.length === 0 ? <EmptyState icon={Library} title="Build your library" text="Build the study knowledge base or import a source, and your lessons will cite it." /> : (
            <div className="space-y-2">
              {shown.map((s) => (
                <Card key={s.id} className="flex flex-wrap items-center gap-3 py-3">
                  <div className="min-w-0 flex-1"><p className="truncate font-medium text-ink">{s.title}</p><p className="truncate text-xs text-muted">{s.location}</p></div>
                  <Badge tone={s.status === "ready" ? "good" : "warn"}>{s.status}</Badge><Badge>{s.license}</Badge>
                  {s.kind === "web" && <Button size="sm" variant="ghost" aria-label="Refresh source" onClick={async () => { try { await api.post(`/api/knowledge/${s.id}/refresh`); toast("good", "Source refreshed."); } catch (e) { fail(e); } refresh(); }}><RefreshCw className="size-4" /></Button>}
                  <Button size="sm" variant="ghost" aria-label={`Delete ${s.title}`} onClick={() => setRemoving(s)}><Trash2 className="size-4" /></Button>
                </Card>
              ))}
              {sources.length > shown.length && <p className="text-sm text-muted">Showing {shown.length} of {sources.length}. Use the filter to narrow the list.</p>}
            </div>
          )}
        </section>
      </div>
      <ConfirmDialog open={!!removing} onClose={() => setRemoving(null)} title="Delete this source?" text={`“${removing?.title}” and its indexed passages will be removed from the library.`} confirmLabel="Delete source"
        onConfirm={async () => { try { await api.del(`/api/knowledge/${removing!.id}`); toast("good", "Source deleted."); refresh(); } catch (e) { fail(e); } setRemoving(null); }} />
    </>
  );
}
