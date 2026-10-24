import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { toast } from "sonner";
import { Braces, Brain, Download, FileJson, FileText, Layers, NotebookPen, AudioLines, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, PageHeader } from "@/components/common";
import { useApi } from "@/hooks/useApi";
import { ApiError, download, exportUrl } from "@/services/api";
import type { Lecture } from "@/types";

const GROUPS = [
  { key: "transcript", title: "Transcript", icon: AudioLines, desc: "Full timestamped transcript", formats: [["txt", "TXT"], ["docx", "DOCX"], ["srt", "SRT subtitles"]] },
  { key: "summary", title: "Summary", icon: FileText, desc: "Executive, quick & detailed summary", formats: [["pdf", "PDF"], ["docx", "DOCX"], ["md", "Markdown"]] },
  { key: "notes", title: "Study notes", icon: NotebookPen, desc: "Structured, exam-ready notes", formats: [["pdf", "PDF"], ["docx", "DOCX"], ["md", "Markdown"], ["txt", "TXT"]] },
  { key: "quiz", title: "Quiz questions", icon: Brain, desc: "Latest quiz with answer key", formats: [["pdf", "PDF"], ["docx", "DOCX"], ["json", "JSON"]] },
  { key: "flashcards", title: "Flashcards", icon: Layers, desc: "Front, back, difficulty, your rating", formats: [["csv", "CSV"]] },
  { key: "json", title: "Structured data", icon: Braces, desc: "Everything about the lecture as JSON", formats: [["json", "JSON"]] },
] as const;

export default function ExportCenter() {
  const loc = useLocation() as { state?: { lectureId?: string } };
  const { data, loading } = useApi<{ items: Lecture[] }>("/api/lectures?status=completed&sort=newest");
  const [lid, setLid] = useState<string>("");
  const [busy, setBusy] = useState<string | null>(null);
  useEffect(() => {
    if (!lid && data?.items.length) setLid(loc.state?.lectureId && data.items.some((l) => l.id === loc.state?.lectureId) ? loc.state.lectureId : data.items[0].id);
  }, [data, lid, loc.state]);

  const dl = async (kind: string, fmt: string) => {
    const key = `${kind}.${fmt}`;
    setBusy(key);
    try {
      const url = kind === "flashcards" || kind === "json" ? exportUrl(lid, kind) : exportUrl(lid, kind, fmt);
      const name = await download(url, `${kind}.${fmt}`);
      toast.success(`Downloaded ${name}`);
    } catch (e) { toast.error((e as ApiError).message); } finally { setBusy(null); }
  };

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader icon={<Download />} title="Export Center" description="Download your learning materials. Files contain the actual generated content with clear filenames." />
      {loading ? <Skeleton className="h-64" /> : !data?.items.length ? (
        <EmptyState icon={<FileJson />} title="Nothing to export yet" description="Exports become available once a lecture has finished processing." />
      ) : (
        <>
          <Card className="mb-6 p-4">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
              <span className="text-sm font-medium">Lecture</span>
              <Select value={lid} onValueChange={setLid}>
                <SelectTrigger className="sm:max-w-md" aria-label="Choose lecture"><SelectValue placeholder="Choose a lecture" /></SelectTrigger>
                <SelectContent>{data.items.map((l) => <SelectItem key={l.id} value={l.id}>{l.title}</SelectItem>)}</SelectContent>
              </Select>
            </div>
          </Card>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {GROUPS.map(({ key, title, icon: Icon, desc, formats }) => (
              <Card key={key} className="card-hover">
                <CardHeader>
                  <div className="mb-1 w-fit rounded-xl bg-gradient-to-br from-indigo-500/20 to-violet-500/20 p-2.5 text-primary"><Icon className="h-5 w-5" /></div>
                  <CardTitle>{title}</CardTitle>
                  <CardDescription>{desc}</CardDescription>
                </CardHeader>
                <CardContent className="flex flex-wrap gap-2">
                  {formats.map(([fmt, label]) => (
                    <Button key={fmt} size="sm" variant="outline" disabled={!lid || !!busy} onClick={() => dl(key, fmt)}>
                      {busy === `${key}.${fmt}` ? <Loader2 className="animate-spin" /> : <Download />}{label}
                    </Button>
                  ))}
                </CardContent>
              </Card>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
