import { Progress } from "@/components/ui/progress";
import { StepIcon } from "@/components/common";
import { cn } from "@/utils/cn";
import type { StepState } from "@/types";

export function ProcessingSteps({ steps, order, labels, progress, currentStepProgress, compact }: {
  steps: Record<string, StepState>; order: string[]; labels: Record<string, string>; progress: number;
  currentStepProgress?: number | null; compact?: boolean;
}) {
  return (
    <div className="space-y-4">
      <div>
        <div className="mb-1.5 flex items-center justify-between text-sm">
          <span className="font-medium">Overall progress</span>
          <span className="tabular-nums text-muted-foreground">{progress}%</span>
        </div>
        <Progress value={progress} className="h-2.5" />
      </div>
      <ol className={cn("grid gap-2", compact ? "sm:grid-cols-3" : "sm:grid-cols-2 lg:grid-cols-3")}>
        {order.map((key, i) => {
          const st = steps[key] || { status: "pending", error: null };
          return (
            <li key={key} className={cn("flex items-start gap-2.5 rounded-xl border px-3 py-2.5 text-sm transition-colors",
              st.status === "running" && "border-primary/50 bg-primary/5",
              st.status === "failed" && "border-destructive/40 bg-destructive/5",
              st.status === "completed" && "bg-card")}
            >
              <StepIcon status={st.status} />
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-2">
                  <span className={cn("font-medium", st.status === "pending" && "text-muted-foreground")}>{i + 1}. {labels[key] || key}</span>
                  {st.status === "running" && currentStepProgress ? <span className="text-xs tabular-nums text-primary">{Math.round(currentStepProgress * 100)}%</span> : null}
                  {st.status === "skipped" && <span className="text-xs text-muted-foreground">skipped</span>}
                </div>
                {st.error && <p className="mt-0.5 text-xs text-destructive">{st.error}</p>}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
