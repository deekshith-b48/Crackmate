"use client";
import { UserPlus } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { useProfiles } from "@/lib/profile";

export function NoProfile() {
  const { loading } = useProfiles();
  if (loading) return <div className="h-40 animate-shimmer rounded-[var(--radius-card)] shimmer" aria-label="Loading your profile" />; // do not flash "no profile" while it loads
  return <EmptyState icon={UserPlus} title="Start with your resume" text="Create a profile first. CrackMate uses it to teach what your projects and skills involve." action={<Link href="/setup/"><Button variant="primary">Set up my profile</Button></Link>} />;
}
