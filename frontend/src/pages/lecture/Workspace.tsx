import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { NavLink, Outlet, useNavigate, useParams, Link } from "react-router-dom";
import { toast } from "sonner";
import {
  AudioLines, Brain, ChevronLeft, FileText, Gauge, Layers, LayoutGrid, MessagesSquare, Network, NotebookPen, Pause, Play, RefreshCw, Rewind, FastForward, Volume2, Clock, Languages, Cpu,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorNote, ModeBadge, StatusBadge } from "@/components/common";
import { useApi, useInterval } from "@/hooks/useApi";
import { ApiError, mediaUrl, post } from "@/services/api";
import { formatDuration, formatTs } from "@/utils/format";
import { cn } from "@/utils/cn";
import type { Lecture } from "@/types";
import type { Player, WorkspaceCtx } from "./context";

const TABS = [
  { to: "", label: "Overview", icon: LayoutGrid, end: true },
  { to: "transcript", label: "Transcript", icon: AudioLines },
  { to: "summary", label: "Summary", icon: FileText },
  { to: "notes", label: "Notes", icon: NotebookPen },
  { to: "chat", label: "AI Chat", icon: MessagesSquare },
  { to: "quiz", label: "Quiz", icon: Brain },
  { to: "flashcards", label: "Flashcards", icon: Layers },
  { to: "knowledge", label: "Knowledge Map", icon: Network },
];

const SPEEDS = [1, 1.25, 1.5, 2, 0.75];

export default function Workspace() {
  const { id } = useParams();
  const nav = useNavigate();
  const { data, error, reload } = useApi<{ lecture: Lecture }>(`/api/lectures/${id}`, [id]);
  const lecture = data?.lecture;
  const busy = lecture?.status === "processing" || lecture?.status === "queued";
  useInterval(() => reload(true), 2500, !!busy);

  // ---- audio player ----
  const audioRef = useRef<HTMLAudioElement>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [audioError, setAudioError] = useState(false);
  const available = !!lecture?.has_audio && !!lecture?.steps?.extract_audio && lecture.steps.extract_audio.status === "completed" && !audioError;

  const seek = useCallback((t: number, play = true) => {
    const a = audioRef.current;
    if (!a) return;
    a.currentTime = Math.max(0, t);
    setCurrentTime(a.currentTime);
    if (play) a.play().catch(() => {});
  }, []);
  const toggle = useCallback(() => {
    const a = audioRef.current;
    if (!a) return;
    if (a.paused) a.play().catch(() => toast.error("Couldn't play the audio.")); else a.pause();
  }, []);
  const player: Player = { currentTime, duration: duration || lecture?.duration || 0, playing, seek, toggle, available };
  const jumpTo = useCallback((t: number) => { nav(`/app/lectures/${id}/transcript?t=${Math.floor(t)}`); seek(t); }, [id, nav, seek]);

  useEffect(() => {
    if (audioRef.current) audioRef.current.playbackRate = speed;
  }, [speed]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || (e.target as HTMLElement)?.isContentEditable) return;
      if (e.code === "Space" && available) { e.preventDefault(); toggle(); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [available, toggle]);

  const ctx: WorkspaceCtx | null = useMemo(() => (lecture ? { lecture, reload, player, jumpTo } : null), [lecture, reload, player, jumpTo]);

  const retry = async () => {
    try { await post(`/api/lectures/${id}/reprocess`); toast.success("Processing restarted"); reload(true); }
    catch (e) { toast.error((e as ApiError).message); }
  };

  if (error) return <ErrorNote message={error.status === 404 ? "This lecture doesn't exist or you don't have access to it." : error.message} onRetry={() => reload()} />;
  if (!lecture || !ctx)
    return (
      <div className="space-y-4"><Skeleton className="h-6 w-32" /><Skeleton className="h-9 w-2/3" /><Skeleton className="h-10 w-full" /><Skeleton className="h-80 w-full" /></div>
    );

  return (
    <div className={cn(available && "pb-20")}>
      <Link to="/app/library" className="mb-3 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"><ChevronLeft className="h-4 w-4" />Library</Link>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h1 className="text-2xl font-bold tracking-tight sm:text-[28px]">{lecture.title}</h1>
          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs text-muted-foreground">
            <StatusBadge status={lecture.status} />
            {lecture.status === "completed" && <ModeBadge mode={lecture.mode} />}
            {lecture.subject && <span className="font-medium text-foreground/80">{lecture.subject}</span>}
            <span className="inline-flex items-center gap-1"><Clock className="h-3.5 w-3.5" />{formatDuration(lecture.duration)}</span>
            {lecture.language && <span className="inline-flex items-center gap-1"><Languages className="h-3.5 w-3.5" />{lecture.language.toUpperCase()}</span>}
            {lecture.transcription && <span className="inline-flex items-center gap-1"><Cpu className="h-3.5 w-3.5" />{lecture.transcription.model}</span>}
          </div>
        </div>
        {lecture.status === "failed" && <Button variant="outline" onClick={retry}><RefreshCw />Retry processing</Button>}
      </div>

      <nav className="no-scrollbar -mx-4 mt-5 overflow-x-auto border-b px-4 sm:mx-0 sm:px-0" aria-label="Lecture sections">
        <div className="flex min-w-max gap-1">
          {TABS.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={label} to={to ? `/app/lectures/${id}/${to}` : `/app/lectures/${id}`} end={end}
              className={({ isActive }) => cn("relative flex items-center gap-2 px-3 pb-3 pt-1 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground",
                isActive && "text-foreground after:absolute after:inset-x-2 after:-bottom-px after:h-0.5 after:rounded-full after:bg-gradient-to-r after:from-indigo-500 after:to-violet-500")}
            >
              <Icon className="h-4 w-4" />{label}
            </NavLink>
          ))}
        </div>
      </nav>

      <div className="mt-6"><Outlet context={ctx} /></div>

      {lecture.has_audio && lecture.steps?.extract_audio?.status === "completed" && (
        <audio
          ref={audioRef}
          src={mediaUrl(lecture.id)}
          preload="metadata"
          onTimeUpdate={(e) => setCurrentTime(e.currentTarget.currentTime)}
          onLoadedMetadata={(e) => setDuration(e.currentTarget.duration)}
          onPlay={() => setPlaying(true)}
          onPause={() => setPlaying(false)}
          onError={() => setAudioError(true)}
        />
      )}

      {available && (
        <div className="fixed inset-x-0 bottom-[calc(64px+env(safe-area-inset-bottom))] z-20 border-t bg-background/90 backdrop-blur-xl lg:bottom-0 lg:left-64">
          <div className="mx-auto flex max-w-7xl items-center gap-2 px-4 py-2.5 sm:gap-3 sm:px-6">
            <Button size="icon" variant="ghost" onClick={() => seek(currentTime - 10, playing)} aria-label="Back 10 seconds" className="hidden sm:inline-flex"><Rewind /></Button>
            <Button size="icon" onClick={toggle} aria-label={playing ? "Pause" : "Play"} className="h-10 w-10 rounded-full bg-gradient-to-br from-indigo-500 to-violet-600 text-white">
              {playing ? <Pause className="!h-5 !w-5" /> : <Play className="!h-5 !w-5 translate-x-px" />}
            </Button>
            <Button size="icon" variant="ghost" onClick={() => seek(currentTime + 10, playing)} aria-label="Forward 10 seconds" className="hidden sm:inline-flex"><FastForward /></Button>
            <span className="w-12 text-right font-mono text-xs tabular-nums text-muted-foreground">{formatTs(currentTime)}</span>
            <input type="range" min={0} max={player.duration || 0} step={0.1} value={currentTime} onChange={(e) => seek(Number(e.target.value), playing)}
              className="h-1.5 flex-1 cursor-pointer accent-[hsl(var(--primary))]" aria-label="Seek" />
            <span className="w-12 font-mono text-xs tabular-nums text-muted-foreground">{formatTs(player.duration)}</span>
            <Button size="sm" variant="ghost" onClick={() => setSpeed(SPEEDS[(SPEEDS.indexOf(speed) + 1) % SPEEDS.length])} aria-label="Playback speed" className="tabular-nums">
              <Gauge />{speed}x
            </Button>
            <Volume2 className="hidden h-4 w-4 text-muted-foreground md:block" />
          </div>
        </div>
      )}
    </div>
  );
}
