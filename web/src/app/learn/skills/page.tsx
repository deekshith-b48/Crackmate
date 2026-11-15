"use client";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { LessonPanel } from "@/components/learn/LessonPanel";
import { NoProfile } from "@/components/learn/NoProfile";
import { PageHeader } from "@/components/shell/PageHeader";
import { Field } from "@/components/ui/Field";
import { Tabs } from "@/components/ui/Tabs";
import { api } from "@/lib/api";
import { useProfiles } from "@/lib/profile";
import type { TopicList } from "@/lib/types";
import { useQueryParam } from "@/lib/useQueryParam";

export default function Skills() {
  const { active } = useProfiles();
  const pid = active?.id;
  const { data } = useQuery({ queryKey: ["topics", pid], queryFn: () => api.get<TopicList>(`/api/profiles/${pid}/lessons/topics`), enabled: !!pid });
  const [topic, setTopic] = useState("");
  const [level, setLevel] = useState("Basics");
  const fromUrl = useQueryParam("topic");
  const levelFromUrl = useQueryParam("level");
  useEffect(() => { if (fromUrl) setTopic(fromUrl); }, [fromUrl]);
  useEffect(() => { if (levelFromUrl) setLevel(levelFromUrl); }, [levelFromUrl]);
  useEffect(() => { if (!topic && data) setTopic(data.groups[0]?.topics[0] ?? ""); }, [data, topic]);

  return (
    <>
      <PageHeader title="Skills" description="Work through one concept at a time, from the basics to advanced." />
      {!pid ? <NoProfile /> : (
        <div className="space-y-6">
          <div className="flex flex-wrap items-end gap-6">
            <Field label="Topic" htmlFor="topic" className="min-w-72">
              <select id="topic" value={topic} onChange={(e) => setTopic(e.target.value)} className="h-10 w-full rounded-[var(--radius-control)] border border-line bg-surface px-3 text-sm text-ink">
                {data?.groups.map((g) => <optgroup key={g.title} label={g.title}>{g.topics.map((t) => <option key={t} value={t}>{t}</option>)}</optgroup>)}
              </select>
            </Field>
            <div><p className="mb-1.5 text-sm font-medium text-ink">Level</p><div className="-mb-6"><Tabs tabs={(data?.levels ?? ["Basics", "Intermediate", "Advanced"]).map((l) => ({ id: l, label: l }))} value={level} onChange={setLevel} /></div></div>
          </div>
          {data && <p className="text-sm text-muted">{data.shared_lessons} shared lessons ready to load instantly. Build more with <code className="font-mono text-[13px]">python -m core.pregen</code>.</p>}
          {topic && <LessonPanel key={`${topic}:${level}`} pid={pid} lessonRef={{ kind: "skill", topic, level }} />}
        </div>
      )}
    </>
  );
}
