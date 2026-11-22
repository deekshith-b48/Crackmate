"use client";
import { Loader2 } from "lucide-react";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/shell/PageHeader";
import { DangerZone } from "@/components/setup/DangerZone";
import { ProfileForm } from "@/components/setup/ProfileForm";
import { ProjectsTab } from "@/components/setup/ProjectsTab";
import { ResumeWizard } from "@/components/setup/ResumeWizard";
import { Tabs } from "@/components/ui/Tabs";
import { useToast } from "@/components/ui/Toast";
import { useProfiles } from "@/lib/profile";
import { useProfile } from "@/lib/queries";
import { useQueryParam } from "@/lib/useQueryParam";

type Tab = "profile" | "projects" | "new" | "delete";

export default function Setup() {
  const { active, loading, setActive, refresh } = useProfiles();
  const { data: record } = useProfile(active?.id);
  const [tab, setTab] = useState<Tab>("profile");
  const toast = useToast();
  const wanted = useQueryParam("tab");
  useEffect(() => { if (wanted === "new") setTab("new"); }, [wanted]); // the sidebar button opens "Add another resume" directly

  const created = (id: string) => {
    setActive(id);
    refresh();
    setTab("profile");
    toast("good", "Profile saved. Review and correct the details before generating lessons.");
  };

  if (loading) return <div className="flex justify-center py-24 text-muted"><Loader2 className="size-6 animate-spin" aria-label="Loading" /></div>;

  if (!active) {
    return (
      <>
        <PageHeader title="Upload your resume to start" description="CrackMate turns your resume into lessons, practice and a plan. Upload it, review what it found, and you are ready to learn." />
        <ResumeWizard onCreated={created} />
      </>
    );
  }

  return (
    <>
      <PageHeader title="Resume and profile" description="Review what CrackMate knows about your experience before it creates study material." />
      <Tabs<Tab> tabs={[{ id: "profile", label: "Profile" }, { id: "projects", label: "Projects" }, { id: "new", label: "Add another resume" }, { id: "delete", label: "Delete" }]} value={tab} onChange={setTab} />
      {tab === "new" && <ResumeWizard onCreated={created} />}
      {tab === "delete" && <DangerZone id={active.id} />}
      {record && tab === "profile" && <ProfileForm key={`${record.id}:${record.revision}`} record={record} />}
      {record && tab === "projects" && <ProjectsTab key={`${record.id}:${record.revision}`} record={record} />}
    </>
  );
}
