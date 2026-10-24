import { useCallback, useRef, useState, type DragEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { CheckCircle2, FileAudio, FileVideo, Info, Loader2, ShieldCheck, UploadCloud, X, ArrowRight, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Textarea } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { PageHeader, ErrorNote } from "@/components/common";
import { ProcessingSteps } from "@/components/ProcessingSteps";
import { useAuth } from "@/hooks/useAuth";
import { useSystemStatus } from "@/hooks/useSystemStatus";
import { useInterval } from "@/hooks/useApi";
import { ApiError, get, uploadWithProgress } from "@/services/api";
import { formatBytes, LANGUAGES } from "@/utils/format";
import { cn } from "@/utils/cn";
import type { Lecture, LectureStatusResponse } from "@/types";

const AUDIO = ["mp3", "wav", "m4a", "aac", "ogg", "oga", "opus", "flac", "weba"];
const VIDEO = ["mp4", "mov", "webm", "mkv", "m4v"];
const ACCEPT = [...AUDIO, ...VIDEO].map((e) => "." + e).join(",");

export default function Upload() {
  const { user } = useAuth();
  const { status: sys } = useSystemStatus();
  const nav = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [drag, setDrag] = useState(false);
  const [title, setTitle] = useState("");
  const [subject, setSubject] = useState("");
  const [description, setDescription] = useState("");
  const [language, setLanguage] = useState(user?.preferences.default_language || "auto");
  const [uploadPct, setUploadPct] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [lecture, setLecture] = useState<Lecture | null>(null);
  const [status, setStatus] = useState<LectureStatusResponse | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const maxMb = sys?.max_upload_mb ?? 500;

  const pick = useCallback((f: File | undefined | null) => {
    setError("");
    if (!f) return;
    const ext = f.name.split(".").pop()?.toLowerCase() || "";
    if (![...AUDIO, ...VIDEO].includes(ext)) {
      setError(`".${ext}" is not supported. Use MP3, WAV, M4A, OGG, FLAC, MP4, MOV, WebM or MKV.`);
      return;
    }
    if (f.size === 0) return setError("That file is empty.");
    if (f.size > maxMb * 1024 * 1024) return setError(`That file is ${formatBytes(f.size)}. The limit is ${maxMb} MB.`);
    setFile(f);
    if (!title) setTitle(f.name.replace(/\.[^.]+$/, "").replace(/[_-]+/g, " "));
  }, [maxMb, title]);

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDrag(false);
    pick(e.dataTransfer.files?.[0]);
  };

  const start = async () => {
    if (!file) return;
    setError("");
    setUploadPct(0);
    const form = new FormData();
    form.append("file", file);
    form.append("title", title);
    form.append("subject", subject);
    form.append("description", description);
    form.append("language", language);
    abortRef.current = new AbortController();
    try {
      const r = await uploadWithProgress<{ lecture: Lecture }>("/api/lectures/upload", form, setUploadPct, abortRef.current.signal);
      setLecture(r.lecture);
      toast.success("Upload complete. Processing started.");
    } catch (e) {
      setError((e as ApiError).message);
      setUploadPct(null);
    }
  };

  const poll = async () => {
    if (!lecture) return;
    try {
      const st = await get<LectureStatusResponse>(`/api/lectures/${lecture.id}/status`);
      setStatus(st);
      if (st.status === "completed") toast.success("Lecture processed! Your study materials are ready.");
      if (st.status === "failed") toast.error(st.error || "Processing failed.");
    } catch {
      /* transient */
    }
  };
  const active = !!lecture && (!status || status.status === "queued" || status.status === "processing");
  useInterval(poll, 2000, active);

  const reset = () => {
    setFile(null); setLecture(null); setStatus(null); setUploadPct(null); setTitle(""); setSubject(""); setDescription(""); setError("");
  };

  const isVideo = file && VIDEO.includes(file.name.split(".").pop()?.toLowerCase() || "");
  const uploading = uploadPct !== null && !lecture;

  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader icon={<UploadCloud />} title="Upload a lecture" description="Audio or video. We'll transcribe it and generate your study materials automatically." />

      {!lecture ? (
        <div className="grid gap-6 lg:grid-cols-[1.3fr_1fr]">
          <Card>
            <CardContent className="space-y-5 p-5">
              <div
                role="button"
                tabIndex={0}
                aria-label="Choose a lecture file or drop it here"
                onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && inputRef.current?.click()}
                onClick={() => !uploading && inputRef.current?.click()}
                onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
                onDragLeave={() => setDrag(false)}
                onDrop={onDrop}
                className={cn("group relative flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed px-6 py-12 text-center transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  drag ? "border-primary bg-primary/10" : "border-border hover:border-primary/60 hover:bg-secondary/40")}
              >
                <input ref={inputRef} type="file" accept={ACCEPT} className="hidden" onChange={(e) => pick(e.target.files?.[0])} />
                {file ? (
                  <div className="flex w-full items-center gap-3 rounded-xl border bg-card p-3 text-left">
                    <span className="rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 p-2.5 text-white">{isVideo ? <FileVideo className="h-5 w-5" /> : <FileAudio className="h-5 w-5" />}</span>
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-medium">{file.name}</div>
                      <div className="text-xs text-muted-foreground">{formatBytes(file.size)} · {isVideo ? "video (audio will be extracted)" : "audio"}</div>
                    </div>
                    {!uploading && (
                      <button type="button" onClick={(e) => { e.stopPropagation(); setFile(null); }} className="rounded-md p-1 text-muted-foreground hover:bg-secondary hover:text-foreground" aria-label="Remove file"><X className="h-4 w-4" /></button>
                    )}
                  </div>
                ) : (
                  <>
                    <div className="mb-4 rounded-2xl bg-gradient-to-br from-indigo-500/20 to-violet-500/20 p-4 text-primary transition-transform group-hover:scale-110"><UploadCloud className="h-8 w-8" /></div>
                    <p className="font-medium">Drag & drop your recording here</p>
                    <p className="mt-1 text-sm text-muted-foreground">or <span className="text-primary">browse files</span></p>
                    <p className="mt-4 text-xs text-muted-foreground">MP3, WAV, M4A, OGG, FLAC · MP4, MOV, WebM, MKV · up to {maxMb} MB</p>
                  </>
                )}
              </div>

              {uploadPct !== null && (
                <div>
                  <div className="mb-1.5 flex justify-between text-sm"><span className="flex items-center gap-2"><Loader2 className="h-4 w-4 animate-spin text-primary" />Uploading…</span><span className="tabular-nums">{uploadPct}%</span></div>
                  <Progress value={uploadPct} />
                  {uploadPct === 100 && <p className="mt-1.5 text-xs text-muted-foreground">Verifying the file on the server…</p>}
                </div>
              )}
              {error && <ErrorNote message={error} />}

              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-1.5 sm:col-span-2">
                  <Label htmlFor="title">Lecture title</Label>
                  <Input id="title" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Lecture 4 — Hidden Markov Models" maxLength={200} />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="subject">Subject <span className="text-muted-foreground">(optional)</span></Label>
                  <Input id="subject" value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="e.g. Speech Recognition" maxLength={100} />
                </div>
                <div className="space-y-1.5">
                  <Label>Language</Label>
                  <Select value={language} onValueChange={setLanguage}>
                    <SelectTrigger aria-label="Lecture language"><SelectValue /></SelectTrigger>
                    <SelectContent>{LANGUAGES.map((l) => <SelectItem key={l.code} value={l.code}>{l.name}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
                <div className="space-y-1.5 sm:col-span-2">
                  <Label htmlFor="desc">Description <span className="text-muted-foreground">(optional)</span></Label>
                  <Textarea id="desc" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Course, professor, topics… helps the AI with context" maxLength={2000} rows={3} />
                </div>
              </div>
              <div className="flex gap-2">
                <Button className="flex-1" size="lg" variant="gradient" disabled={!file || uploading} loading={uploading} onClick={start}>
                  <UploadCloud /> Upload & process
                </Button>
                {uploading && <Button size="lg" variant="outline" onClick={() => abortRef.current?.abort()}>Cancel</Button>}
              </div>
            </CardContent>
          </Card>

          <div className="space-y-4">
            <Card>
              <CardHeader><CardTitle className="text-sm">What happens next</CardTitle></CardHeader>
              <CardContent className="space-y-3 text-sm text-muted-foreground">
                {["We check the file and extract the audio with FFmpeg", `Speech is transcribed with ${sys?.transcription_model || "Whisper"}`, sys?.ai_enabled ? `${sys.chat_model} writes summaries, notes, a quiz, flashcards and a knowledge map` : "Demo mode builds extractive summaries, keyword notes, cloze quizzes and flashcards (no AI model configured)", "You can study while it works. We'll show live progress"].map((t, i) => (
                  <div key={i} className="flex gap-3"><span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/15 text-xs font-semibold text-primary">{i + 1}</span><span>{t}</span></div>
                ))}
              </CardContent>
            </Card>
            <Card className="border-primary/20 bg-primary/5">
              <CardContent className="flex gap-3 p-4 text-xs leading-5 text-muted-foreground">
                <ShieldCheck className="h-5 w-5 shrink-0 text-primary" />
                <span>{sys?.data_disclosure || "Loading data handling details…"}</span>
              </CardContent>
            </Card>
          </div>
        </div>
      ) : (
        <Card className="animate-fade-up">
          <CardHeader className="flex-row items-start justify-between gap-4 space-y-0">
            <div>
              <CardTitle className="text-lg">{lecture.title}</CardTitle>
              <CardDescription>
                {status?.status === "completed" ? "All done! Your study materials are ready." : status?.status === "failed" ? "Processing failed." : status?.current_step_label ? `${status.current_step_label}…` : "Queued, starting shortly…"}
              </CardDescription>
            </div>
            {status?.status === "completed" ? <CheckCircle2 className="h-8 w-8 text-success" /> : status?.status === "failed" ? null : <Loader2 className="h-6 w-6 animate-spin text-primary" />}
          </CardHeader>
          <CardContent className="space-y-5">
            <ProcessingSteps steps={status?.steps || lecture.steps} order={status?.steps_order || lecture.steps_order} labels={status?.step_labels || lecture.step_labels}
              progress={status?.progress ?? 0} currentStepProgress={status?.current_step_progress} />
            {status?.error && status.status === "failed" && <ErrorNote message={status.error} />}
            <div className="flex flex-wrap gap-2">
              <Button variant="gradient" onClick={() => nav(`/app/lectures/${lecture.id}${status?.status === "completed" ? "/summary" : ""}`)}>
                {status?.status === "completed" ? "Open lecture workspace" : "Open workspace now"} <ArrowRight />
              </Button>
              <Button variant="outline" onClick={reset}><RotateCcw /> Upload another</Button>
              <Button asChild variant="ghost"><Link to="/app">Back to dashboard</Link></Button>
            </div>
            <p className="flex items-center gap-2 text-xs text-muted-foreground"><Info className="h-3.5 w-3.5" />You can leave this page. Processing continues in the background.</p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
