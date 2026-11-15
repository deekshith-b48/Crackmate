"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, ExternalLink, FlaskConical, GitBranch, RefreshCw, ShieldAlert, Trash2 } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/Dialog";
import { Input } from "@/components/ui/Field";
import { StepGenerating } from "@/components/ui/StepGenerating";
import { IdentityPicker } from "@/components/analyse/IdentityPicker";
import { useToast } from "@/components/ui/Toast";
import { api } from "@/lib/api";
import { useJob } from "@/lib/stream";
import type { ProjectCard, RepoView } from "@/lib/types";

/** Reads the real code behind a project, so questions are about what you built rather than a resume line. No model is used. */
export function RepoInsights({ pid, projectId }: { pid: string; projectId: string }) {
  const client = useQueryClient();
  const toast = useToast();
  const key = ["career-overview", pid];
  const { data } = useQuery({ queryKey: key, queryFn: () => api.get<ProjectCard[]>(`/api/profiles/${pid}/career/overview`) });
  const card = data?.find((c) => c.project_id === projectId);
  const repo = card?.repo ?? null;
  const [url, setUrl] = useState("");
  const [me, setMe] = useState<string[] | null>(null);
  const [removing, setRemoving] = useState(false);
  const job = useJob<{ changed: boolean; repo: RepoView }>();

  async function analyse(force = false) {
    const out = await job.run(`/api/profiles/${pid}/career/repos`, { project_id: projectId, url: repo?.url ?? url, force });
    if (!out) return;
    client.invalidateQueries({ queryKey: key });
    toast("good", out.changed ? "Repository analysed." : "Already up to date: no new commits.");
  }
  async function remove() {
    await api.del(`/api/profiles/${pid}/career/repos/${projectId}`);
    client.invalidateQueries({ queryKey: key });
    setRemoving(false);
    toast("good", "Repository removed.");
  }

  if (job.status === "running") return <StepGenerating title="Reading your repository" steps={job.steps} running startedAt={job.startedAt} />;
  if (!repo) {
    return (
      <Card className="space-y-3">
        <div className="flex items-center gap-2"><GitBranch className="size-5 text-brand-600" /><h2 className="font-semibold text-ink">Add your GitHub repo to unlock code insights</h2></div>
        <p className="text-sm text-muted">CrackMate reads your real code, dependencies and commit history to check your resume claims, find what you built, and spot talking points. Public repositories only; nothing is sent to a model.</p>
        <div className="flex flex-wrap gap-2"><Input aria-label="GitHub repository URL" placeholder="https://github.com/you/your-project" value={url} onChange={(e) => setUrl(e.target.value)} className="max-w-md" /><Button variant="primary" onClick={() => analyse()} disabled={!url.trim()}>Analyse repository</Button></div>
        {job.status === "error" && <p role="alert" className="text-sm text-bad">{job.error}</p>}
      </Card>
    );
  }
  const langs = Object.entries(repo.facts.languages).slice(0, 3);
  const choosing = me ?? (repo.ownership.identified ? null : []);
  return (
    <Card className="space-y-6">
      <div className="flex flex-wrap items-center gap-2">
        <GitBranch className="size-5 text-brand-600" />
        <a href={repo.url} target="_blank" rel="noreferrer noopener" className="inline-flex items-center gap-1 font-semibold text-ink hover:underline">{repo.url.replace("https://github.com/", "")}<ExternalLink className="size-3.5" /></a>
        <Badge>{repo.facts.loc.toLocaleString()} lines</Badge>{langs.map(([l, n]) => <Badge key={l}>{l} · {n.toLocaleString()}</Badge>)}
        <span className="ml-auto flex gap-1"><Button size="sm" variant="ghost" onClick={() => analyse(true)} aria-label="Re-read repository"><RefreshCw className="size-4" /> Refresh</Button><Button size="sm" variant="ghost" onClick={() => setRemoving(true)} aria-label="Remove repository"><Trash2 className="size-4" /></Button></span>
      </div>
      {job.status === "error" && <p role="alert" className="text-sm text-bad">{job.error}</p>}

      <section>
        <h3 className="mb-2 text-sm font-semibold text-ink">Stack found in your code</h3>
        <div className="flex flex-wrap gap-2">{repo.facts.technologies.map((t) => <Badge key={t.name} tone="brand" className="cursor-help" ><span title={`${t.evidence.map((e) => `${e.kind}: ${e.file}`).join("\n")}`}>{t.name} · {Math.round(t.confidence * 100)}%</span></Badge>)}</div>
        <p className="mt-1.5 text-xs text-muted">Percent is how sure we are. 90% means imported in code, 80% means declared in a dependency or config file. Hover for the evidence.</p>
      </section>

      {(card!.unsupported.length > 0 || card!.undeclared.length > 0) && (
        <section className="grid gap-4 sm:grid-cols-2">
          {card!.unsupported.length > 0 && <div className="rounded-[var(--radius-control)] bg-warn-tint p-3"><p className="mb-1.5 flex items-center gap-2 text-sm font-medium text-ink"><AlertTriangle className="size-4 text-warn" /> On your resume, not found in the code</p><div className="flex flex-wrap gap-1.5">{card!.unsupported.map((t) => <Badge key={t} tone="warn">{t}</Badge>)}</div><p className="mt-2 text-xs text-muted">It may live in another repo, but expect to be asked where. Be ready to explain.</p></div>}
          {card!.undeclared.length > 0 && <div className="rounded-[var(--radius-control)] bg-brand-50 p-3"><p className="mb-1.5 text-sm font-medium text-ink">In your code, missing from your resume</p><div className="flex flex-wrap gap-1.5">{card!.undeclared.map((t) => <Badge key={t} tone="brand">{t}</Badge>)}</div><p className="mt-2 text-xs text-muted">Consider adding these to the project on your resume.</p></div>}
        </section>
      )}

      <section>
        <h3 className="mb-2 text-sm font-semibold text-ink">What you built</h3>
        {choosing ? (
          <IdentityPicker pid={pid} projectId={projectId} repo={repo} initial={me ?? []} onSaved={() => setMe(null)} />
        ) : (
          <div className="space-y-2 text-sm">
            <p><span className="text-2xl font-semibold text-ink">{Math.round(repo.ownership.share * 100)}%</span> of added lines · {repo.ownership.your_commits} of {repo.ownership.commits} commits are yours. <button className="text-brand-600 underline" onClick={() => setMe(repo.identities)}>Change</button></p>
            {repo.ownership.files_not_yours.length > 0 && <p className="text-muted">Mostly written by others but you may still be asked about them: {repo.ownership.files_not_yours.slice(0, 4).map((f) => <code key={f.path} className="mx-1 rounded bg-slate-100 px-1 font-mono text-xs">{f.path}</code>)}</p>}
          </div>
        )}
      </section>

      <section>
        <h3 className="mb-2 text-sm font-semibold text-ink">Talking points: where the hard problems were</h3>
        {repo.hotspots.length === 0 ? <p className="text-sm text-muted">Not enough history to find hotspots yet.</p> : (
          <ul className="divide-y divide-line">{repo.hotspots.slice(0, 5).map((h) => <li key={h.path} className="flex items-center gap-3 py-2 text-sm"><code className="min-w-0 flex-1 truncate font-mono text-xs">{h.path}</code><span className="text-muted">{h.commits} commits · {h.churn.toLocaleString()} lines changed</span></li>)}</ul>
        )}
        <p className="mt-1.5 text-xs text-muted">Files changed most often usually hide a story: what broke, and how you fixed it. Prepare one.</p>
      </section>

      <section>
        <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-ink"><FlaskConical className="size-4" /> Security check</h3>
        {repo.secrets.length === 0 ? <p className="flex items-center gap-2 text-sm text-good"><CheckCircle2 className="size-4" /> No committed secrets found.</p> : (
          <div className="space-y-2 rounded-[var(--radius-control)] border border-red-200 bg-bad-tint p-3" role="alert">
            <p className="flex items-center gap-2 text-sm font-medium text-bad"><ShieldAlert className="size-4" /> {repo.secrets.length} possible secret(s) in your repo. Rotate them, then remove them from history.</p>
            <ul className="space-y-1 text-sm">{repo.secrets.slice(0, 6).map((s, i) => <li key={i}><code className="font-mono text-xs">{s.file}:{s.line}</code> · {s.kind}{s.preview && <span className="text-muted"> · {s.preview}</span>}</li>)}</ul>
          </div>
        )}
      </section>
      <p className="text-xs text-muted">Analysed commit {repo.commit.slice(0, 7)} on {new Date(repo.indexed_at).toLocaleDateString()}. Refresh re-reads it only if there are new commits.</p>
      <ConfirmDialog open={removing} onClose={() => setRemoving(false)} onConfirm={remove} title="Remove this repository?" text="The downloaded copy and its analysis are deleted from this computer. Your profile and lessons are not affected." confirmLabel="Remove" />
    </Card>
  );
}
