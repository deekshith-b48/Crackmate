import { UserPlus } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";

export function NoProfile() {
  return <EmptyState icon={UserPlus} title="Start with your resume" text="Create a profile first. CrackMate uses it to teach what your projects and skills involve." action={<Link href="/setup/"><Button variant="primary">Set up my profile</Button></Link>} />;
}
