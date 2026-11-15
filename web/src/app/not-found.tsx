import { Compass } from "lucide-react";
import Link from "next/link";
import { PageHeader } from "@/components/shell/PageHeader";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";

export default function NotFound() {
  return (
    <>
      <PageHeader title="Page not found" />
      <EmptyState icon={Compass} title="This page is not available yet" text="It may still be on its way, or the link is out of date. Head back to your dashboard." action={<Link href="/"><Button variant="primary">Go to Home</Button></Link>} />
    </>
  );
}
