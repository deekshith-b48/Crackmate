import { GitBranch } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";

export function NeedRepo({ what }: { what: string }) {
  return <EmptyState icon={GitBranch} title="Add a GitHub repo to unlock this" text={`${what} come from your real code and commit history. Attach a public repository to a project and CrackMate reads it, with no model involved.`} action={<Link href="/learn/projects/"><Button variant="primary">Attach a repository</Button></Link>} />;
}
