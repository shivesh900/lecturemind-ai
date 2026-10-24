import type { ReactNode } from "react";
import { Loader2, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/common";
import { Skeleton } from "@/components/ui/skeleton";
import type { Lecture } from "@/types";

/** Shown in a tab while the lecture is still processing / failed / material missing. */
export function NotReady({ lecture, what, icon, onGenerate, generating }: { lecture: Lecture; what: string; icon: ReactNode; onGenerate?: () => void; generating?: boolean }) {
  if (lecture.status === "processing" || lecture.status === "queued")
    return (
      <EmptyState icon={<Loader2 className="animate-spin" />} title={`Generating ${what}…`}
        description={`${lecture.current_step_label || "Queued"} · ${lecture.progress}% complete. This page updates automatically.`} />
    );
  return (
    <EmptyState icon={icon} title={`No ${what} yet`}
      description={lecture.status === "failed" ? `Processing failed: ${lecture.error || "unknown error"}` : `The ${what} for this lecture hasn't been generated.`}
      action={onGenerate && <Button onClick={onGenerate} loading={generating}><RefreshCw />Generate {what}</Button>} />
  );
}

export function TabSkeleton() {
  return (
    <div className="space-y-3">
      <Skeleton className="h-8 w-48" />
      <Skeleton className="h-24 w-full" />
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-5/6" />
      <Skeleton className="h-4 w-4/6" />
    </div>
  );
}

export function TimeChip({ t, onClick }: { t: number | null | undefined; onClick?: (t: number) => void }) {
  if (t == null) return null;
  const m = Math.floor(t / 60), s = Math.floor(t % 60);
  return (
    <button type="button" onClick={() => onClick?.(t)} className="inline-flex shrink-0 items-center rounded-md bg-primary/10 px-1.5 py-0.5 font-mono text-[11px] font-medium text-primary transition-colors hover:bg-primary/20" aria-label={`Jump to ${m} minutes ${s} seconds`}>
      {String(m).padStart(2, "0")}:{String(s).padStart(2, "0")}
    </button>
  );
}
