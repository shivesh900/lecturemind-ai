import type { ReactNode } from "react";
import { AlertTriangle, CheckCircle2, CircleDashed, Clock, FlaskConical, Loader2, Sparkles, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { cn } from "@/utils/cn";
import type { LectureStatus, StepStatus } from "@/types";

export function PageHeader({ title, description, actions, icon }: { title: ReactNode; description?: ReactNode; actions?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="flex items-start gap-3">
        {icon && <div className="mt-0.5 rounded-xl bg-primary/15 p-2.5 text-primary [&_svg]:h-5 [&_svg]:w-5">{icon}</div>}
        <div>
          <h1 className="text-2xl font-bold tracking-tight sm:text-[28px]">{title}</h1>
          {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
        </div>
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function EmptyState({ icon, title, description, action, className }: { icon: ReactNode; title: string; description?: ReactNode; action?: ReactNode; className?: string }) {
  return (
    <div className={cn("flex flex-col items-center justify-center rounded-2xl border border-dashed bg-card/40 px-6 py-14 text-center", className)}>
      <div className="mb-4 rounded-2xl bg-gradient-to-br from-indigo-500/20 to-violet-500/20 p-4 text-primary [&_svg]:h-7 [&_svg]:w-7">{icon}</div>
      <h3 className="text-base font-semibold">{title}</h3>
      {description && <p className="mt-1.5 max-w-md text-sm text-muted-foreground">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function StatusBadge({ status }: { status: LectureStatus }) {
  const map = {
    completed: { v: "success" as const, icon: <CheckCircle2 />, label: "Ready" },
    processing: { v: "default" as const, icon: <Loader2 className="animate-spin" />, label: "Processing" },
    queued: { v: "secondary" as const, icon: <Clock />, label: "Queued" },
    failed: { v: "destructive" as const, icon: <XCircle />, label: "Failed" },
  }[status];
  return <Badge variant={map.v}>{map.icon}{map.label}</Badge>;
}

export function ModeBadge({ mode }: { mode?: string }) {
  if (mode === "demo")
    return <Badge variant="warning" title="Generated without an AI model (keyword / extractive methods)"><FlaskConical />Demo mode</Badge>;
  if (mode === "ai") return <Badge variant="violet"><Sparkles />AI generated</Badge>;
  return null;
}

export function StepIcon({ status }: { status: StepStatus }) {
  if (status === "completed") return <CheckCircle2 className="h-4 w-4 text-success" />;
  if (status === "running") return <Loader2 className="h-4 w-4 animate-spin text-primary" />;
  if (status === "failed") return <XCircle className="h-4 w-4 text-destructive" />;
  if (status === "skipped") return <CircleDashed className="h-4 w-4 text-muted-foreground" />;
  return <CircleDashed className="h-4 w-4 text-muted-foreground/50" />;
}

export function ErrorNote({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex items-start gap-3 rounded-xl border border-destructive/30 bg-destructive/10 p-4 text-sm">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />
      <div className="flex-1">{message}</div>
      {onRetry && <Button size="sm" variant="outline" onClick={onRetry}>Retry</Button>}
    </div>
  );
}

export function ConfirmDialog({ open, onOpenChange, title, description, confirmLabel = "Confirm", destructive, onConfirm, loading }: {
  open: boolean; onOpenChange: (o: boolean) => void; title: string; description?: ReactNode; confirmLabel?: string;
  destructive?: boolean; onConfirm: () => void; loading?: boolean;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {description && <DialogDescription>{description}</DialogDescription>}
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button variant={destructive ? "destructive" : "default"} onClick={onConfirm} loading={loading}>{confirmLabel}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
