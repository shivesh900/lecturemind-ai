import { useMemo, useState } from "react";
import { toast } from "sonner";
import { AlertTriangle, Eye, EyeOff, Loader2, MessageSquareWarning, RefreshCw, ShieldAlert, ShieldCheck, Sparkles, Swords, Type, UserX } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/input";
import { EmptyState, ErrorNote } from "@/components/common";
import { useApi } from "@/hooks/useApi";
import { ApiError, post } from "@/services/api";
import { cn } from "@/utils/cn";
import type { FlaggedSegment, SafetyCategory, SafetyCheckResult, SafetyMatch, SafetyReport, SafetySeverity } from "@/types";
import { useWorkspace } from "./context";
import { NotReady, TabSkeleton, TimeChip } from "./shared";

export const CATEGORY_LABEL: Record<SafetyCategory, string> = { threat: "Threat", hate: "Hate", insult: "Insult", profanity: "Profanity" };
const SEV_STYLE: Record<SafetySeverity, string> = {
  high: "border-transparent bg-red-500/15 text-red-400",
  medium: "border-transparent bg-amber-500/15 text-amber-400",
  low: "border-transparent bg-yellow-500/10 text-yellow-500/90",
};

export function SeverityBadge({ s }: { s: SafetySeverity }) {
  return <Badge className={cn("uppercase tracking-wide", SEV_STYLE[s])}>{s}</Badge>;
}

/** Render text with matched spans masked (or revealed) and underlined. */
export function MaskedText({ text, matches, reveal }: { text: string; matches: SafetyMatch[]; reveal: boolean }) {
  const spans = [...matches].sort((a, b) => a.start - b.start).filter((m, i, arr) => i === 0 || m.start >= arr[i - 1].end);
  const out: React.ReactNode[] = [];
  let pos = 0;
  spans.forEach((m, i) => {
    if (m.start > pos) out.push(text.slice(pos, m.start));
    const word = text.slice(m.start, m.end);
    const shown = reveal || m.kind === "phrase" ? word : m.masked;
    out.push(
      <span key={i} title={`${CATEGORY_LABEL[m.category]} · ${m.severity} · ${m.label}`}
        className={cn("rounded px-0.5 font-medium underline decoration-2 underline-offset-4",
          m.severity === "high" ? "bg-red-500/10 decoration-red-500/80" : "bg-amber-500/10 decoration-amber-500/80")}>{shown}</span>,
    );
    pos = m.end;
  });
  if (pos < text.length) out.push(text.slice(pos));
  return <>{out}</>;
}

const SUMMARY: { key: "total" | SafetyCategory; label: string; icon: React.ElementType; tone: string }[] = [
  { key: "total", label: "Flagged sentences", icon: ShieldAlert, tone: "from-indigo-500/20 to-violet-500/10 text-indigo-300" },
  { key: "threat", label: "Threats", icon: Swords, tone: "from-red-500/20 to-red-500/5 text-red-400" },
  { key: "profanity", label: "Profanity", icon: Type, tone: "from-amber-500/20 to-amber-500/5 text-amber-400" },
  { key: "insult", label: "Insults / harassment", icon: UserX, tone: "from-orange-500/20 to-orange-500/5 text-orange-400" },
];

function sourceLabel(s: string) { return s === "ai_moderation" ? "AI moderation" : "Lexicon"; }

function SegmentRow({ f, reveal, onSeek }: { f: FlaggedSegment; reveal: boolean; onSeek: (t: number) => void }) {
  const matches = f.flags.flatMap((x) => x.matches);
  const ai = f.flags.filter((x) => x.source === "ai_moderation");
  return (
    <div className={cn("flex gap-3 px-4 py-3.5 sm:gap-4", f.severity === "high" ? "shadow-[inset_3px_0_0_rgb(239_68_68/0.8)]" : "shadow-[inset_3px_0_0_rgb(245_158_11/0.8)]")}>
      <div className="w-14 shrink-0 pt-0.5"><TimeChip t={f.start} onClick={onSeek} /></div>
      <div className="min-w-0 flex-1 space-y-2">
        <p className="text-[15px] leading-7 text-foreground/90"><MaskedText text={f.text} matches={matches} reveal={reveal} /></p>
        <div className="flex flex-wrap items-center gap-1.5 text-xs">
          <SeverityBadge s={f.severity} />
          {f.categories.map((c) => <Badge key={c} variant="outline">{CATEGORY_LABEL[c]}</Badge>)}
          {f.sources.map((s) => <Badge key={s} variant={s === "ai_moderation" ? "violet" : "secondary"}>{s === "ai_moderation" && <Sparkles />}{sourceLabel(s)}</Badge>)}
          {ai.map((a) => <span key={a.category} className="text-muted-foreground">AI score {Math.round((a.score || 0) * 100)}%</span>)}
        </div>
      </div>
    </div>
  );
}

function CheckBox() {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState<SafetyCheckResult | null>(null);
  const [reveal, setReveal] = useState(false);
  const run = async () => {
    if (!text.trim()) return;
    setBusy(true);
    try { setRes(await post<SafetyCheckResult>("/api/safety/check", { text })); }
    catch (e) { toast.error((e as ApiError).message); } finally { setBusy(false); }
  };
  return (
    <Card className="p-5">
      <div className="mb-3 flex items-center gap-2"><MessageSquareWarning className="h-4 w-4 text-primary" /><h3 className="font-semibold">Check a sentence</h3></div>
      <Textarea value={text} onChange={(e) => setText(e.target.value)} rows={3} maxLength={2000} placeholder="Type or paste a sentence, e.g. “Do that again and I will beat you.”"
        onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) run(); }} aria-label="Sentence to check" />
      <div className="mt-3 flex items-center justify-between gap-2">
        <span className="text-xs text-muted-foreground">Ctrl + Enter to check</span>
        <Button size="sm" onClick={run} loading={busy} disabled={!text.trim()}><ShieldCheck />Check</Button>
      </div>
      {res && (
        <div className={cn("mt-4 rounded-xl border p-3.5", res.flagged ? "border-red-500/30 bg-red-500/5" : "border-emerald-500/30 bg-emerald-500/5")} aria-live="polite">
          {res.flagged ? (
            <>
              <div className="flex flex-wrap items-center gap-1.5 text-sm font-medium">
                <AlertTriangle className="h-4 w-4 text-red-400" />Harsh language found
                {res.severity && <SeverityBadge s={res.severity} />}
                {res.categories.map((c) => <Badge key={c} variant="outline">{CATEGORY_LABEL[c]}</Badge>)}
                <button type="button" onClick={() => setReveal(!reveal)} className="ml-auto inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
                  {reveal ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}{reveal ? "Hide words" : "Reveal words"}</button>
              </div>
              <p className="mt-2 text-sm leading-6"><MaskedText text={res.text} matches={res.matches} reveal={reveal} /></p>
              <p className="mt-2 text-xs text-muted-foreground">Detected by {res.sources.map(sourceLabel).join(" + ")}
                {res.flags.filter((f) => f.source === "ai_moderation").map((f) => ` · AI ${CATEGORY_LABEL[f.category]} ${Math.round((f.score || 0) * 100)}%`).join("")}</p>
            </>
          ) : (
            <div className="flex items-center gap-2 text-sm"><ShieldCheck className="h-4 w-4 text-emerald-400" />No harsh or threatening language detected.</div>
          )}
          {res.moderation.status === "failed" && <p className="mt-1 text-xs text-amber-400">AI moderation was unavailable; lexicon result only.</p>}
        </div>
      )}
    </Card>
  );
}

export default function SafetyTab() {
  const { lecture, jumpTo } = useWorkspace();
  const ready = lecture.steps?.transcribe?.status === "completed" && (lecture.status === "completed" || lecture.status === "failed" || lecture.steps?.content_safety?.status === "completed");
  const { data, error, loading, setData } = useApi<SafetyReport>(ready ? `/api/lectures/${lecture.id}/safety` : null, [ready]);
  const [reveal, setReveal] = useState(false);
  const [filter, setFilter] = useState<SafetyCategory | "all">("all");
  const [scanning, setScanning] = useState(false);

  const list = useMemo(() => (data?.flagged || []).filter((f) => filter === "all" || f.categories.includes(filter)), [data, filter]);

  if (!ready) return <NotReady lecture={lecture} what="safety scan" icon={<ShieldAlert />} />;
  if (error) return <ErrorNote message={error.message} />;
  if (loading || !data) return <TabSkeleton />;

  const rescan = async () => {
    setScanning(true);
    try { const r = await post<SafetyReport>(`/api/lectures/${lecture.id}/safety/rescan`); setData(r); toast.success(`Re-scanned ${r.segments_scanned} segments`); }
    catch (e) { toast.error((e as ApiError).message); } finally { setScanning(false); }
  };
  const s = data.summary;
  const mod = data.moderation;

  return (
    <div className="grid gap-6 xl:grid-cols-[1fr_360px]">
      <div className="min-w-0 space-y-4">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {SUMMARY.map(({ key, label, icon: Icon, tone }) => (
            <Card key={key} className="relative overflow-hidden p-4">
              <div className={cn("absolute inset-0 bg-gradient-to-br opacity-60", tone.split(" ").slice(0, 2).join(" "))} />
              <div className="relative">
                <Icon className={cn("h-5 w-5", tone.split(" ")[2])} />
                <div className="mt-3 text-2xl font-bold tabular-nums">{key === "total" ? s.total_flagged : s.by_category[key]}</div>
                <div className="text-xs text-muted-foreground">{label}</div>
              </div>
            </Card>
          ))}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {(["all", "threat", "profanity", "insult", "hate"] as const).map((c) => (
            <button key={c} type="button" onClick={() => setFilter(c)}
              className={cn("rounded-full border px-3 py-1 text-xs font-medium transition-colors", filter === c ? "border-primary/50 bg-primary/15 text-primary" : "text-muted-foreground hover:text-foreground")}>
              {c === "all" ? `All (${s.total_flagged})` : `${CATEGORY_LABEL[c]} (${s.by_category[c]})`}
            </button>
          ))}
          <div className="ml-auto flex items-center gap-2">
            <Button size="sm" variant="outline" onClick={() => setReveal(!reveal)}>{reveal ? <EyeOff /> : <Eye />}{reveal ? "Mask words" : "Reveal words"}</Button>
            <Button size="sm" variant="outline" onClick={rescan} disabled={scanning}>{scanning ? <Loader2 className="animate-spin" /> : <RefreshCw />}Re-scan</Button>
          </div>
        </div>

        {list.length === 0 ? (
          <EmptyState icon={<ShieldCheck />} title={s.total_flagged ? "Nothing in this category" : "No harsh language found"}
            description={`${data.segments_scanned} transcript segments scanned. No profanity, insults, threats or hate speech were detected.`} />
        ) : (
          <Card className="divide-y overflow-hidden">
            {list.map((f) => <SegmentRow key={f.segment_idx} f={f} reveal={reveal} onSeek={jumpTo} />)}
          </Card>
        )}
      </div>

      <div className="space-y-4">
        <CheckBox />
        <Card className="space-y-2 p-5 text-xs leading-5 text-muted-foreground">
          <div className="flex items-center gap-2 text-sm font-semibold text-foreground"><ShieldAlert className="h-4 w-4 text-primary" />How this works</div>
          <p><span className="font-medium text-foreground">Lexicon</span> (always on): English, Hinglish and Tamil-English abusive words, including disguised spellings like f*ck or sh1t, plus threat phrases such as “I will kill you” or “watch your back”.</p>
          <p><span className="font-medium text-foreground">AI moderation</span>:{" "}
            {mod.status === "used" ? <>on ({mod.model}). It catches context that word lists miss.</> :
              mod.status === "failed" ? <span className="text-amber-400">failed on the last scan, so these are lexicon-only results.</span> :
                <>off. Set OPENAI_API_KEY to add context-aware checks. Text is then sent to OpenAI.</>}</p>
          <p>Word lists can't read sarcasm or quotes, so treat flags as pointers to review, not verdicts.</p>
          <p className="pt-1">Scanned {new Date(data.scanned_at).toLocaleString()}</p>
        </Card>
      </div>
    </div>
  );
}
