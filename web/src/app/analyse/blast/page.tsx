"use client";
import { Radar } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { NoProfile } from "@/components/learn/NoProfile";
import { PageHeader } from "@/components/shell/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Field } from "@/components/ui/Field";
import { lessonHref, useBlast, useSignals } from "@/lib/career";
import { useProfiles } from "@/lib/profile";
import { useQueryParam } from "@/lib/useQueryParam";

export default function BlastRadius() {
  const { active } = useProfiles();
  const { data: signals } = useSignals(active?.id);
  const [topic, setTopic] = useState("");
  const fromUrl = useQueryParam("topic");
  useEffect(() => { if (fromUrl) setTopic(fromUrl); }, [fromUrl]);
  useEffect(() => { if (!topic && signals?.topics[0]) setTopic(signals.topics[0].topic); }, [signals, topic]);
  const { data } = useBlast(active?.id, topic);
  const total = data ? data.concepts.length + data.technologies.length : 0;

  return (
    <>
      <PageHeader title="Concept blast radius" description="Pick a concept to see everything that depends on it. If you are weak here, this is how far the damage spreads." />
      {!active ? <NoProfile /> : !signals?.topics.length ? <EmptyState icon={Radar} title="Add a project first" text="The blast radius is computed from the technologies in your projects." /> : (
        <div className="space-y-6">
          <Field label="Concept" htmlFor="concept" className="max-w-sm">
            <select id="concept" value={topic} onChange={(e) => setTopic(e.target.value)} className="h-10 w-full rounded-[var(--radius-control)] border border-line bg-surface px-3 text-sm text-ink">
              {[...signals.topics].sort((a, b) => a.topic.localeCompare(b.topic)).map((t) => <option key={t.topic}>{t.topic}</option>)}
            </select>
          </Field>
          {data && (
            <>
              <Card className="border-brand-200 bg-brand-50/40">
                <p className="text-lg text-ink">Not knowing <strong>{data.topic}</strong> affects <strong>{data.questions}</strong> saved question{data.questions === 1 ? "" : "s"} across <strong>{data.projects.length}</strong> of your project{data.projects.length === 1 ? "" : "s"}, and {total} other concept{total === 1 ? "" : "s"} or technolog{total === 1 ? "y" : "ies"} build on it.</p>
                {data.questions === 0 && <p className="mt-2 text-sm text-muted">Question counts come from lessons you have saved. Generate lessons for these topics to see them.</p>}
                <div className="mt-4"><Link href={lessonHref(data.topic)}><Button variant="primary" size="sm">Learn {data.topic}</Button></Link></div>
              </Card>
              <div className="grid gap-4 md:grid-cols-3">
                {([["Projects that depend on it", data.projects, "brand"], ["Technologies that need it", data.technologies, "neutral"], ["Concepts built on it", data.concepts, "warn"]] as const).map(([title, items, tone]) => (
                  <Card key={title}><h2 className="mb-3 text-sm font-semibold text-ink">{title} <span className="font-normal text-muted">({items.length})</span></h2>
                    {items.length ? <div className="flex flex-wrap gap-1.5">{items.map((x) => title.startsWith("Concepts") ? <Link key={x} href={`/analyse/blast/?topic=${encodeURIComponent(x)}`}><Badge tone={tone}>{x}</Badge></Link> : <Badge key={x} tone={tone}>{x}</Badge>)}</div> : <p className="text-sm text-muted">None.</p>}
                  </Card>
                ))}
              </div>
            </>
          )}
        </div>
      )}
    </>
  );
}
