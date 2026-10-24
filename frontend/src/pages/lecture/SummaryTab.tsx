import { useState } from "react";
import { toast } from "sonner";
import { BookMarked, Download, FileText, Lightbulb, ListChecks, RefreshCw, Sigma, Sparkles, Target, MessageSquareQuote, Copy } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { ErrorNote, ModeBadge } from "@/components/common";
import { useApi } from "@/hooks/useApi";
import { ApiError, download, exportUrl, post } from "@/services/api";
import type { SummaryDoc } from "@/types";
import { useWorkspace } from "./context";
import { NotReady, TabSkeleton, TimeChip } from "./shared";

function ListCard({ title, icon, items }: { title: string; icon: React.ReactNode; items: React.ReactNode[] }) {
  if (!items.length) return null;
  return (
    <Card>
      <CardHeader className="pb-2"><CardTitle className="flex items-center gap-2 text-sm"><span className="text-primary [&_svg]:h-4 [&_svg]:w-4">{icon}</span>{title}</CardTitle></CardHeader>
      <CardContent><ul className="space-y-2">{items.map((it, i) => <li key={i} className="flex gap-2.5 text-sm leading-6"><span className="mt-2.5 h-1 w-1 shrink-0 rounded-full bg-primary" /><div className="min-w-0">{it}</div></li>)}</ul></CardContent>
    </Card>
  );
}

export default function SummaryTab() {
  const { lecture, reload: reloadLecture, jumpTo } = useWorkspace();
  const has = lecture.available?.summary;
  const { data, error, loading, reload } = useApi<SummaryDoc>(has ? `/api/lectures/${lecture.id}/summary` : null, [has, lecture.status]);
  const [view, setView] = useState<"concise" | "detailed">("concise");
  const [regen, setRegen] = useState(false);

  const regenerate = async () => {
    setRegen(true);
    try { await post(`/api/lectures/${lecture.id}/summary`); toast.success("Regenerating summary and dependent materials…"); await reloadLecture(true); }
    catch (e) { toast.error((e as ApiError).message); } finally { setRegen(false); }
  };
  const dl = async (fmt: string) => {
    try { const n = await download(exportUrl(lecture.id, "summary", fmt), `summary.${fmt}`); toast.success(`Downloaded ${n}`); }
    catch (e) { toast.error((e as ApiError).message); }
  };

  if (!has || lecture.status === "processing" && lecture.steps.summary?.status !== "completed")
    return <NotReady lecture={lecture} what="summary" icon={<FileText />} onGenerate={lecture.status === "completed" ? regenerate : undefined} generating={regen} />;
  if (error) return <ErrorNote message={error.message} onRetry={() => reload()} />;
  if (loading || !data) return <TabSkeleton />;
  const s = data.summary;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Tabs value={view} onValueChange={(v) => setView(v as "concise" | "detailed")}>
          <TabsList><TabsTrigger value="concise"><Sparkles />Concise</TabsTrigger><TabsTrigger value="detailed"><FileText />Detailed</TabsTrigger></TabsList>
        </Tabs>
        <div className="flex flex-wrap items-center gap-2">
          <ModeBadge mode={data.mode} />
          <Button size="sm" variant="outline" onClick={async () => { await navigator.clipboard.writeText(s.executive_summary + "\n\n" + s.quick_summary.join("\n")); toast.success("Copied"); }}><Copy />Copy</Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild><Button size="sm" variant="outline"><Download />Export</Button></DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => dl("pdf")}>PDF</DropdownMenuItem>
              <DropdownMenuItem onClick={() => dl("docx")}>Word (DOCX)</DropdownMenuItem>
              <DropdownMenuItem onClick={() => dl("md")}>Markdown</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          <Button size="sm" variant="ghost" onClick={regenerate} loading={regen} disabled={lecture.status !== "completed"}><RefreshCw />Regenerate</Button>
        </div>
      </div>

      <Card className="relative overflow-hidden border-primary/30">
        <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/10 via-violet-500/5 to-transparent" />
        <CardContent className="relative p-6">
          <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-primary"><Target className="h-4 w-4" />Executive summary</div>
          <p className="text-[15px] leading-7">{s.executive_summary}</p>
        </CardContent>
      </Card>

      {view === "concise" ? (
        <div className="grid gap-5 lg:grid-cols-2">
          <ListCard title="Five-line summary" icon={<ListChecks />} items={s.quick_summary} />
          <ListCard title="Key takeaways" icon={<Lightbulb />} items={s.key_takeaways} />
          <ListCard title="Main topics" icon={<BookMarked />} items={s.main_topics.map((t) => <span key={t.title}><strong>{t.title}</strong>{t.description && <span className="text-muted-foreground"> — {t.description}</span>}</span>)} />
          {data.chapters.length > 0 && (
            <ListCard title="Chapters" icon={<FileText />} items={data.chapters.map((c) => <span key={c.start} className="flex items-start gap-2"><TimeChip t={c.start} onClick={jumpTo} /><span>{c.title}</span></span>)} />
          )}
        </div>
      ) : (
        <div className="grid gap-5 lg:grid-cols-[1.6fr_1fr]">
          <div className="space-y-5">
            {s.detailed_summary.map((sec, i) => (
              <Card key={i}>
                <CardHeader className="pb-2"><CardTitle>{sec.heading}</CardTitle></CardHeader>
                <CardContent><p className="whitespace-pre-line text-sm leading-7 text-foreground/90">{sec.content}</p></CardContent>
              </Card>
            ))}
            <ListCard title="Important arguments & explanations" icon={<MessageSquareQuote />} items={s.arguments} />
          </div>
          <div className="space-y-5">
            <ListCard title="Definitions" icon={<BookMarked />} items={s.definitions.map((d) => <span key={d.term}><strong>{d.term}</strong>: {d.definition}</span>)} />
            <ListCard title="Formulas & concepts" icon={<Sigma />} items={s.formulas.map((f) => <span key={f.expression}><code className="rounded bg-muted px-1.5 py-0.5 font-mono text-[13px] text-primary">{f.expression}</code>{f.meaning && <span className="text-muted-foreground"> — {f.meaning}</span>}</span>)} />
            <ListCard title="Examples mentioned" icon={<Lightbulb />} items={s.examples} />
            <ListCard title="Key takeaways" icon={<ListChecks />} items={s.key_takeaways} />
          </div>
        </div>
      )}
      <p className="text-xs text-muted-foreground">{data.mode === "ai" ? `Generated by ${data.model || "the AI model"} from this lecture's transcript only (chunked map-reduce).` : "Demo mode: sentences were selected from the transcript by keyword scoring. No AI model was used."}</p>
    </div>
  );
}
