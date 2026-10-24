import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { AudioLines, Check, Copy, Download, FileDown, Pencil, Save, Search, X, Crosshair, ChevronUp, ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input, Textarea } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { ErrorNote } from "@/components/common";
import { useApi } from "@/hooks/useApi";
import { ApiError, download, exportUrl, patch } from "@/services/api";
import { cn } from "@/utils/cn";
import type { Transcript } from "@/types";
import { useWorkspace } from "./context";
import { NotReady, TabSkeleton, TimeChip } from "./shared";

function highlight(text: string, q: string) {
  if (!q) return text;
  const parts = text.split(new RegExp(`(${q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "gi"));
  return parts.map((p, i) => (p.toLowerCase() === q.toLowerCase() ? <mark key={i} className="rounded bg-warning/40 px-0.5 text-foreground">{p}</mark> : p));
}

export default function TranscriptTab() {
  const { lecture, player } = useWorkspace();
  const ready = lecture.steps?.transcribe?.status === "completed";
  const { data, error, loading, reload, setData } = useApi<Transcript>(ready ? `/api/lectures/${lecture.id}/transcript` : null, [ready]);
  const [q, setQ] = useState("");
  const [editing, setEditing] = useState(false);
  const [drafts, setDrafts] = useState<Record<number, string>>({});
  const [saving, setSaving] = useState(false);
  const [follow, setFollow] = useState(true);
  const [matchIdx, setMatchIdx] = useState(0);
  const [params] = useSearchParams();
  const refs = useRef<Record<number, HTMLDivElement | null>>({});

  const segments = data?.segments || [];
  const activeIdx = useMemo(() => {
    const t = player.currentTime;
    let lo = 0, hi = segments.length - 1, ans = -1;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      if (segments[mid].start <= t + 0.05) { ans = mid; lo = mid + 1; } else hi = mid - 1;
    }
    return ans >= 0 && t <= segments[ans].end + 1.5 ? segments[ans].idx : -1;
  }, [player.currentTime, segments]);

  const matches = useMemo(() => (q.trim().length > 0 ? segments.filter((s) => s.text.toLowerCase().includes(q.trim().toLowerCase())).map((s) => s.idx) : []), [q, segments]);
  useEffect(() => setMatchIdx(0), [q]);
  useEffect(() => {
    if (matches.length) refs.current[matches[matchIdx]]?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [matchIdx, matches]);

  useEffect(() => {
    if (follow && player.playing && activeIdx >= 0 && !editing && !q) refs.current[activeIdx]?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [activeIdx, follow, player.playing, editing, q]);

  // deep link ?t=123
  useEffect(() => {
    const t = Number(params.get("t"));
    if (!segments.length || !params.get("t") || Number.isNaN(t)) return;
    const seg = [...segments].reverse().find((s) => s.start <= t + 0.5) || segments[0];
    setTimeout(() => refs.current[seg.idx]?.scrollIntoView({ block: "center", behavior: "smooth" }), 150);
  }, [params, segments]);

  if (!ready) return <NotReady lecture={lecture} what="transcript" icon={<AudioLines />} />;
  if (error) return <ErrorNote message={error.message} onRetry={() => reload()} />;
  if (loading || !data) return <TabSkeleton />;

  const copy = async () => {
    await navigator.clipboard.writeText(segments.map((s) => s.text).join("\n"));
    toast.success("Transcript copied to clipboard");
  };
  const save = async () => {
    const changed = Object.entries(drafts).filter(([i, t]) => segments.find((s) => s.idx === Number(i))?.text !== t);
    if (!changed.length) { setEditing(false); return; }
    if (changed.some(([, t]) => !t.trim())) return toast.error("Segments can't be empty.");
    setSaving(true);
    try {
      await patch(`/api/lectures/${lecture.id}/transcript`, { segments: changed.map(([idx, text]) => ({ idx: Number(idx), text })) });
      setData({ ...data, segments: segments.map((s) => (drafts[s.idx] !== undefined ? { ...s, text: drafts[s.idx].trim(), edited: true } : s)) });
      toast.success(`Saved ${changed.length} edited segment${changed.length > 1 ? "s" : ""}`);
      setEditing(false);
      setDrafts({});
    } catch (e) { toast.error((e as ApiError).message); } finally { setSaving(false); }
  };
  const dl = async (fmt: string) => {
    try { const n = await download(exportUrl(lecture.id, "transcript", fmt), `transcript.${fmt}`); toast.success(`Downloaded ${n}`); }
    catch (e) { toast.error((e as ApiError).message); }
  };

  return (
    <div className="space-y-4">
      <Card className="sticky top-16 z-10 p-3 shadow-lg">
        <div className="flex flex-col gap-3 md:flex-row md:items-center">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search in transcript…" className="pl-9 pr-28" aria-label="Search in transcript" />
            {q && (
              <div className="absolute right-1.5 top-1/2 flex -translate-y-1/2 items-center gap-0.5">
                <span className="mr-1 text-xs tabular-nums text-muted-foreground">{matches.length ? `${matchIdx + 1}/${matches.length}` : "0"}</span>
                <Button size="icon" variant="ghost" className="h-7 w-7" disabled={!matches.length} onClick={() => setMatchIdx((matchIdx - 1 + matches.length) % matches.length)} aria-label="Previous match"><ChevronUp /></Button>
                <Button size="icon" variant="ghost" className="h-7 w-7" disabled={!matches.length} onClick={() => setMatchIdx((matchIdx + 1) % matches.length)} aria-label="Next match"><ChevronDown /></Button>
              </div>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <label className="mr-1 flex items-center gap-2 text-xs text-muted-foreground"><Switch checked={follow} onCheckedChange={setFollow} aria-label="Follow playback" /><Crosshair className="h-3.5 w-3.5" />Follow</label>
            {editing ? (
              <>
                <Button size="sm" variant="outline" onClick={() => { setEditing(false); setDrafts({}); }}><X />Cancel</Button>
                <Button size="sm" onClick={save} loading={saving}><Save />Save</Button>
              </>
            ) : (
              <Button size="sm" variant="outline" onClick={() => setEditing(true)}><Pencil />Edit</Button>
            )}
            <Button size="sm" variant="outline" onClick={copy}><Copy />Copy</Button>
            <Button size="sm" variant="outline" onClick={() => dl("txt")}><Download />TXT</Button>
            <Button size="sm" variant="outline" onClick={() => dl("docx")}><FileDown />DOCX</Button>
          </div>
        </div>
      </Card>

      <div className="flex flex-wrap items-center gap-2 px-1 text-xs text-muted-foreground">
        <span>{segments.length} segments</span><span>·</span><span>{data.text.split(/\s+/).length.toLocaleString()} words</span>
        {data.transcription && <><span>·</span><span>transcribed by {data.transcription.model}</span></>}
        {!data.has_speakers && <><span>·</span><span>speaker labels unavailable (the transcription model doesn't do diarization)</span></>}
      </div>

      <Card className="divide-y overflow-hidden">
        {segments.map((s) => {
          const active = s.idx === activeIdx;
          const isMatch = matches.includes(s.idx);
          return (
            <div key={s.idx} ref={(el) => (refs.current[s.idx] = el)}
              className={cn("group flex gap-3 px-4 py-3 transition-colors sm:gap-4", active && "bg-gradient-to-r from-indigo-500/15 to-transparent shadow-[inset_3px_0_0_hsl(var(--primary))]",
                isMatch && matches[matchIdx] === s.idx && "bg-warning/10")}
            >
              <div className="flex w-14 shrink-0 flex-col items-start gap-1 pt-0.5">
                <TimeChip t={s.start} onClick={(t) => player.seek(t)} />
                {s.edited && <span className="flex items-center gap-0.5 text-[10px] text-muted-foreground"><Check className="h-3 w-3" />edited</span>}
              </div>
              <div className="min-w-0 flex-1">
                {s.speaker && <div className="mb-0.5 text-xs font-semibold text-primary">{s.speaker}</div>}
                {editing ? (
                  <Textarea value={drafts[s.idx] ?? s.text} onChange={(e) => setDrafts({ ...drafts, [s.idx]: e.target.value })} rows={Math.max(2, Math.ceil(s.text.length / 90))} className="text-sm leading-6" aria-label={`Segment at ${s.start} seconds`} />
                ) : (
                  <p className={cn("cursor-pointer text-[15px] leading-7 text-foreground/90", active && "text-foreground")} onClick={() => player.seek(s.start)}>{highlight(s.text, q.trim())}</p>
                )}
              </div>
            </div>
          );
        })}
      </Card>
    </div>
  );
}
