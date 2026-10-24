import { Link } from "react-router-dom";
import { AudioLines, Brain, FileText, Layers, MessagesSquare, Network, NotebookPen, ArrowRight, Download } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorNote } from "@/components/common";
import { ProcessingSteps } from "@/components/ProcessingSteps";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/useApi";
import { formatBytes, formatDate, formatDuration } from "@/utils/format";
import type { SummaryDoc } from "@/types";
import { useWorkspace } from "./context";
import { TimeChip } from "./shared";

const LINKS = [
  { to: "transcript", label: "Transcript", desc: "Read, search, edit and play", icon: AudioLines },
  { to: "summary", label: "Summary", desc: "Concise & detailed views", icon: FileText },
  { to: "notes", label: "Smart notes", desc: "Exam-ready, editable", icon: NotebookPen },
  { to: "chat", label: "Ask the lecture", desc: "Grounded answers + timestamps", icon: MessagesSquare },
  { to: "quiz", label: "Quiz", desc: "MCQ, T/F, short & long", icon: Brain },
  { to: "flashcards", label: "Flashcards", desc: "Flip, rate, review", icon: Layers },
  { to: "knowledge", label: "Knowledge map", desc: "Concept graph", icon: Network },
];

export default function OverviewTab() {
  const { lecture, jumpTo } = useWorkspace();
  const done = lecture.status === "completed";
  const summary = useApi<SummaryDoc>(lecture.available?.summary ? `/api/lectures/${lecture.id}/summary` : null, [lecture.available?.summary]);

  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="space-y-6 lg:col-span-2">
        {!done && (
          <Card>
            <CardHeader>
              <CardTitle>{lecture.status === "failed" ? "Processing failed" : "Processing your lecture"}</CardTitle>
              <CardDescription>{lecture.status === "failed" ? "Fix the problem below and retry. Completed steps will not be repeated." : "Each step is saved as it finishes. You can open the transcript as soon as it's ready."}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <ProcessingSteps steps={lecture.steps} order={lecture.steps_order} labels={lecture.step_labels} progress={lecture.progress} />
              {lecture.error && <ErrorNote message={lecture.error} />}
            </CardContent>
          </Card>
        )}

        {summary.data ? (
          <Card>
            <CardHeader>
              <CardTitle>At a glance</CardTitle>
              <CardDescription>Five-line summary</CardDescription>
            </CardHeader>
            <CardContent>
              <ul className="space-y-2.5">
                {summary.data.summary.quick_summary.map((l, i) => (
                  <li key={i} className="flex gap-3 text-sm leading-6"><span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-gradient-to-r from-indigo-400 to-violet-400" />{l}</li>
                ))}
              </ul>
            </CardContent>
          </Card>
        ) : summary.loading ? <Skeleton className="h-48" /> : null}

        {summary.data && summary.data.chapters.length > 0 && (
          <Card>
            <CardHeader><CardTitle>Chapters</CardTitle><CardDescription>Jump to any part of the lecture</CardDescription></CardHeader>
            <CardContent className="space-y-1">
              {summary.data.chapters.map((c, i) => (
                <button key={i} onClick={() => jumpTo(c.start)} className="flex w-full items-start gap-3 rounded-xl p-2.5 text-left transition-colors hover:bg-secondary/60">
                  <TimeChip t={c.start} />
                  <div className="min-w-0"><div className="text-sm font-medium">{c.title}</div><p className="line-clamp-2 text-xs text-muted-foreground">{c.summary}</p></div>
                </button>
              ))}
            </CardContent>
          </Card>
        )}
      </div>

      <div className="space-y-6">
        <Card>
          <CardHeader><CardTitle>Study materials</CardTitle></CardHeader>
          <CardContent className="space-y-1">
            {LINKS.map(({ to, label, desc, icon: Icon }) => (
              <Link key={to} to={to} className="group flex items-center gap-3 rounded-xl p-2 transition-colors hover:bg-secondary/60">
                <span className="rounded-lg bg-primary/15 p-2 text-primary"><Icon className="h-4 w-4" /></span>
                <div className="flex-1"><div className="text-sm font-medium">{label}</div><div className="text-xs text-muted-foreground">{desc}</div></div>
                <ArrowRight className="h-4 w-4 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
              </Link>
            ))}
            <Link to="/app/exports" state={{ lectureId: lecture.id }} className="group flex items-center gap-3 rounded-xl p-2 transition-colors hover:bg-secondary/60">
              <span className="rounded-lg bg-primary/15 p-2 text-primary"><Download className="h-4 w-4" /></span>
              <div className="flex-1"><div className="text-sm font-medium">Export</div><div className="text-xs text-muted-foreground">PDF, DOCX, TXT, CSV, JSON</div></div>
            </Link>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Details</CardTitle></CardHeader>
          <CardContent>
            <dl className="grid grid-cols-2 gap-y-3 text-sm">
              {[
                ["Uploaded", formatDate(lecture.created_at)],
                ["Duration", formatDuration(lecture.duration)],
                ["Type", lecture.kind === "video" ? "Video" : "Audio"],
                ["File size", formatBytes(lecture.file_size)],
                ["Words", lecture.word_count?.toLocaleString() || "—"],
                ["Segments", lecture.segment_count?.toLocaleString() || "—"],
                ["Language", lecture.language?.toUpperCase() || "—"],
                ["Transcriber", lecture.transcription?.model || "—"],
              ].map(([k, v]) => (
                <div key={k}><dt className="text-xs text-muted-foreground">{k}</dt><dd className="truncate font-medium">{v}</dd></div>
              ))}
            </dl>
            {lecture.description && <p className="mt-4 border-t pt-3 text-sm text-muted-foreground">{lecture.description}</p>}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
