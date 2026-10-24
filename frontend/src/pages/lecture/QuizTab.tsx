import { useMemo, useState } from "react";
import { toast } from "sonner";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid } from "recharts";
import { Brain, Check, CheckCircle2, Download, Eye, History, Plus, RotateCcw, Star, Trophy, X, XCircle, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { ErrorNote, ModeBadge } from "@/components/common";
import { useApi } from "@/hooks/useApi";
import { ApiError, download, exportUrl, post } from "@/services/api";
import { cn } from "@/utils/cn";
import { timeAgo } from "@/utils/format";
import type { Quiz, QuizAttempt, QuizQuestion } from "@/types";
import { useWorkspace } from "./context";
import { NotReady, TabSkeleton } from "./shared";

const TYPE_LABEL: Record<string, string> = { mcq: "Multiple choice", true_false: "True / False", short: "Short answer", long: "Long answer" };
const DIFF_VARIANT: Record<string, "success" | "warning" | "destructive"> = { easy: "success", medium: "warning", hard: "destructive" };

function QuestionCard({ q, n, answer, setAnswer, selfMark, setSelfMark, result }: {
  q: QuizQuestion; n: number; answer: string; setAnswer: (v: string) => void; selfMark?: boolean; setSelfMark: (v: boolean) => void;
  result?: { correct: boolean | null; correct_answer: string; explanation: string };
}) {
  const [reveal, setReveal] = useState(false);
  const reviewing = !!result;
  const written = q.type === "short" || q.type === "long";
  return (
    <Card className={cn("animate-fade-up", reviewing && result?.correct === true && "border-success/40", reviewing && result?.correct === false && "border-destructive/40")}>
      <CardContent className="p-5">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/15 text-xs font-bold text-primary">{n}</span>
          <Badge variant="outline">{TYPE_LABEL[q.type]}</Badge>
          <Badge variant={DIFF_VARIANT[q.difficulty]} className="capitalize">{q.difficulty}</Badge>
          {q.important && <Badge variant="violet"><Star />Exam important</Badge>}
          {reviewing && (result?.correct === true ? <CheckCircle2 className="ml-auto h-5 w-5 text-success" /> : result?.correct === false ? <XCircle className="ml-auto h-5 w-5 text-destructive" /> : null)}
        </div>
        <p className="font-medium leading-7">{q.question}</p>

        {(q.type === "mcq" || q.type === "true_false") && (
          <div className={cn("mt-4 grid gap-2", q.type === "true_false" ? "grid-cols-2" : "sm:grid-cols-2")} role="radiogroup" aria-label={`Question ${n} options`}>
            {q.options.map((o, i) => {
              const selected = answer === o;
              const isCorrect = reviewing && o === result!.correct_answer;
              const isWrongPick = reviewing && selected && !isCorrect;
              return (
                <button key={o} type="button" role="radio" aria-checked={selected} disabled={reviewing} onClick={() => setAnswer(o)}
                  className={cn("flex items-center gap-3 rounded-xl border px-3.5 py-3 text-left text-sm transition-all",
                    !reviewing && "hover:border-primary/50 hover:bg-secondary/50",
                    selected && !reviewing && "border-primary bg-primary/10 ring-1 ring-primary",
                    isCorrect && "border-success bg-success/10", isWrongPick && "border-destructive bg-destructive/10")}
                >
                  <span className={cn("flex h-6 w-6 shrink-0 items-center justify-center rounded-md border text-xs font-semibold", selected && "border-primary bg-primary text-primary-foreground", isCorrect && "border-success bg-success text-white")}>
                    {q.type === "mcq" ? "ABCD"[i] : o[0]}
                  </span>
                  <span>{o}</span>
                </button>
              );
            })}
          </div>
        )}

        {written && (
          <div className="mt-4 space-y-3">
            <Textarea value={answer} onChange={(e) => setAnswer(e.target.value)} disabled={reviewing} rows={q.type === "long" ? 5 : 2} placeholder="Write your answer…" aria-label={`Answer to question ${n}`} />
            {!reviewing && (
              <div className="flex flex-wrap items-center gap-2">
                <Button size="sm" variant="outline" onClick={() => setReveal((r) => !r)}><Eye />{reveal ? "Hide" : "Check"} model answer</Button>
                {reveal && (
                  <>
                    <span className="text-xs text-muted-foreground">Did you get it?</span>
                    <Button size="sm" variant={selfMark === true ? "default" : "outline"} onClick={() => setSelfMark(true)}><Check />Yes</Button>
                    <Button size="sm" variant={selfMark === false ? "destructive" : "outline"} onClick={() => setSelfMark(false)}><X />No</Button>
                  </>
                )}
              </div>
            )}
            {(reveal || reviewing) && <div className="rounded-xl border border-primary/30 bg-primary/5 p-3 text-sm"><div className="mb-1 text-xs font-semibold text-primary">Model answer</div>{q.correct_answer}</div>}
          </div>
        )}

        {reviewing && result?.explanation && (
          <div className="mt-4 rounded-xl bg-secondary/60 p-3 text-sm"><span className="font-semibold">Explanation: </span>{result.explanation}</div>
        )}
      </CardContent>
    </Card>
  );
}

export default function QuizTab() {
  const { lecture } = useWorkspace();
  const ready = lecture.available?.quiz || lecture.status === "completed";
  const { data, error, loading, reload } = useApi<{ quizzes: Quiz[]; attempts: QuizAttempt[] }>(ready ? `/api/lectures/${lecture.id}/quizzes` : null, [ready, lecture.status]);
  const [quizId, setQuizId] = useState<string | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [marks, setMarks] = useState<Record<string, boolean>>({});
  const [result, setResult] = useState<QuizAttempt | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [startedAt, setStartedAt] = useState(Date.now());
  const [genOpen, setGenOpen] = useState(false);
  const [gen, setGen] = useState({ difficulty: "mixed", num_mcq: 6, num_true_false: 3, num_short: 2, num_long: 1 });
  const [generating, setGenerating] = useState(false);

  const quizzes = data?.quizzes || [];
  const quiz = quizzes.find((q) => q.id === quizId) || quizzes[0];
  const attempts = useMemo(() => (data?.attempts || []).filter((a) => a.quiz_id === quiz?.id), [data, quiz]);
  const resultMap = useMemo(() => Object.fromEntries((result?.results || []).map((r) => [r.question_id, r])), [result]);

  if (!ready) return <NotReady lecture={lecture} what="quiz" icon={<Brain />} />;
  if (error) return <ErrorNote message={error.message} onRetry={() => reload()} />;
  if (loading || !data) return <TabSkeleton />;

  const retake = () => { setAnswers({}); setMarks({}); setResult(null); setStartedAt(Date.now()); window.scrollTo({ top: 0, behavior: "smooth" }); };
  const submit = async () => {
    if (!quiz) return;
    const unanswered = quiz.questions.filter((q) => (q.type === "mcq" || q.type === "true_false") && !answers[q.id]).length;
    if (unanswered && !confirm(`${unanswered} objective question(s) unanswered. Submit anyway?`)) return;
    setSubmitting(true);
    try {
      const r = await post<QuizAttempt>(`/api/quizzes/${quiz.id}/attempts`, { answers, self_marks: marks, duration_seconds: Math.round((Date.now() - startedAt) / 1000) });
      setResult(r);
      reload(true);
      window.scrollTo({ top: 0, behavior: "smooth" });
      toast.success(`Score: ${r.score}%`);
    } catch (e) { toast.error((e as ApiError).message); } finally { setSubmitting(false); }
  };
  const generate = async () => {
    setGenerating(true);
    try {
      const q = await post<Quiz>(`/api/lectures/${lecture.id}/quiz`, gen);
      await reload(true);
      setQuizId(q.id); retake(); setGenOpen(false);
      toast.success(`New ${gen.difficulty} quiz with ${q.questions.length} questions`);
    } catch (e) { toast.error((e as ApiError).message); } finally { setGenerating(false); }
  };
  const dl = async (fmt: string) => {
    try { const n = await download(exportUrl(lecture.id, "quiz", fmt) + (quiz ? `&quiz_id=${quiz.id}` : ""), `quiz.${fmt}`); toast.success(`Downloaded ${n}`); }
    catch (e) { toast.error((e as ApiError).message); }
  };

  const answered = quiz ? quiz.questions.filter((q) => answers[q.id]?.trim()).length : 0;
  const best = attempts.length ? Math.max(...attempts.map((a) => a.score)) : null;

  return (
    <div className="grid gap-6 xl:grid-cols-[1fr_320px]">
      <div className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            {quizzes.length > 1 && (
              <Select value={quiz?.id} onValueChange={(v) => { setQuizId(v); retake(); }}>
                <SelectTrigger className="w-60" aria-label="Choose quiz"><SelectValue /></SelectTrigger>
                <SelectContent>{quizzes.map((q) => <SelectItem key={q.id} value={q.id}>{q.difficulty} · {q.questions.length} Qs · {timeAgo(q.created_at)}</SelectItem>)}</SelectContent>
              </Select>
            )}
            {quiz && <ModeBadge mode={quiz.mode} />}
          </div>
          <div className="flex gap-2">
            <DropdownMenu>
              <DropdownMenuTrigger asChild><Button size="sm" variant="outline" disabled={!quiz}><Download />Export</Button></DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={() => dl("pdf")}>PDF (with answer key)</DropdownMenuItem>
                <DropdownMenuItem onClick={() => dl("docx")}>Word (DOCX)</DropdownMenuItem>
                <DropdownMenuItem onClick={() => dl("json")}>JSON</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
            <Button size="sm" variant="gradient" onClick={() => setGenOpen(true)} disabled={lecture.status !== "completed"}><Plus />New quiz</Button>
          </div>
        </div>

        {!quiz ? (
          <Card className="p-10 text-center text-sm text-muted-foreground">No quiz yet. Generate one to start practising.</Card>
        ) : (
          <>
            {result ? (
              <Card className="relative overflow-hidden">
                <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/15 via-violet-500/10 to-transparent" />
                <CardContent className="relative flex flex-col items-center gap-4 p-6 text-center sm:flex-row sm:text-left">
                  <div className="relative flex h-24 w-24 items-center justify-center rounded-full border-4 border-primary/30">
                    <svg className="absolute inset-0 -rotate-90" viewBox="0 0 100 100"><circle cx="50" cy="50" r="46" fill="none" stroke="url(#sg)" strokeWidth="8" strokeDasharray={`${result.score * 2.89} 289`} strokeLinecap="round" /><defs><linearGradient id="sg"><stop stopColor="#6366f1" /><stop offset="1" stopColor="#a855f7" /></linearGradient></defs></svg>
                    <span className="text-2xl font-bold">{Math.round(result.score)}%</span>
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center justify-center gap-2 text-lg font-semibold sm:justify-start"><Trophy className="h-5 w-5 text-warning" />{result.score >= 80 ? "Excellent work!" : result.score >= 50 ? "Good effort!" : "Keep practising!"}</div>
                    <p className="mt-1 text-sm text-muted-foreground">{result.correct} of {result.gradable} graded questions correct{result.total > result.gradable ? ` · ${result.total - result.gradable} written answers not self-marked` : ""}. Review the explanations below.</p>
                  </div>
                  <Button onClick={retake}><RotateCcw />Retake</Button>
                </CardContent>
              </Card>
            ) : (
              <Card className="p-4">
                <div className="flex items-center justify-between text-sm"><span className="font-medium">{quiz.title}</span><span className="tabular-nums text-muted-foreground">{answered}/{quiz.questions.length} answered</span></div>
                <Progress value={(answered / quiz.questions.length) * 100} className="mt-2 h-1.5" />
              </Card>
            )}
            {quiz.questions.map((q, i) => (
              <QuestionCard key={q.id + (result ? "r" : "")} q={q} n={i + 1} answer={answers[q.id] || ""} setAnswer={(v) => setAnswers({ ...answers, [q.id]: v })}
                selfMark={marks[q.id]} setSelfMark={(v) => setMarks({ ...marks, [q.id]: v })} result={resultMap[q.id]} />
            ))}
            {!result && <Button size="lg" variant="gradient" className="w-full" onClick={submit} loading={submitting}><CheckCircle2 />Submit answers</Button>}
          </>
        )}
      </div>

      <div className="space-y-4">
        <Card>
          <CardHeader className="pb-2"><CardTitle className="flex items-center gap-2 text-sm"><History className="h-4 w-4 text-primary" />Your attempts</CardTitle><CardDescription>{attempts.length ? `Best ${best}% · ${attempts.length} attempt${attempts.length > 1 ? "s" : ""}` : "No attempts on this quiz yet"}</CardDescription></CardHeader>
          <CardContent>
            {attempts.length > 1 && (
              <div className="mb-3 h-32">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={[...attempts].reverse().map((a, i) => ({ n: i + 1, score: a.score }))} margin={{ left: -28, right: 6, top: 6 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                    <XAxis dataKey="n" fontSize={11} tickLine={false} axisLine={false} stroke="hsl(var(--muted-foreground))" />
                    <YAxis domain={[0, 100]} ticks={[0, 50, 100]} fontSize={11} tickLine={false} axisLine={false} stroke="hsl(var(--muted-foreground))" />
                    <Tooltip contentStyle={{ background: "hsl(var(--popover))", border: "1px solid hsl(var(--border))", borderRadius: 12, fontSize: 12 }} />
                    <Line type="monotone" dataKey="score" stroke="#8b5cf6" strokeWidth={2.5} dot={{ r: 3 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
            <div className="space-y-1.5">
              {attempts.slice(0, 8).map((a) => (
                <div key={a.id} className="flex items-center justify-between rounded-lg bg-secondary/50 px-3 py-2 text-sm">
                  <span className="text-muted-foreground">{timeAgo(a.created_at)}</span>
                  <span className={cn("font-semibold tabular-nums", a.score >= 80 ? "text-success" : a.score >= 50 ? "text-warning" : "text-destructive")}>{a.score}%</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
        {quiz && (
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm">This quiz</CardTitle></CardHeader>
            <CardContent className="space-y-1.5 text-sm">
              {(["mcq", "true_false", "short", "long"] as const).map((t) => {
                const c = quiz.questions.filter((q) => q.type === t).length;
                return c ? <div key={t} className="flex justify-between"><span className="text-muted-foreground">{TYPE_LABEL[t]}</span><span className="font-medium">{c}</span></div> : null;
              })}
              <div className="flex justify-between border-t pt-1.5"><span className="text-muted-foreground">Difficulty</span><span className="font-medium capitalize">{quiz.difficulty}</span></div>
            </CardContent>
          </Card>
        )}
      </div>

      <Dialog open={genOpen} onOpenChange={setGenOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle className="flex items-center gap-2"><Sparkles className="h-5 w-5 text-primary" />Generate a new quiz</DialogTitle><DialogDescription>Questions come only from this lecture's content.</DialogDescription></DialogHeader>
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label>Difficulty</Label>
              <Select value={gen.difficulty} onValueChange={(v) => setGen({ ...gen, difficulty: v })}>
                <SelectTrigger aria-label="Difficulty"><SelectValue /></SelectTrigger>
                <SelectContent><SelectItem value="mixed">Mixed</SelectItem><SelectItem value="easy">Easy</SelectItem><SelectItem value="medium">Medium</SelectItem><SelectItem value="hard">Hard</SelectItem></SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              {([["num_mcq", "MCQs", 20], ["num_true_false", "True / False", 10], ["num_short", "Short answer", 10], ["num_long", "Long answer", 5]] as const).map(([k, label, max]) => (
                <div key={k} className="space-y-1.5">
                  <Label htmlFor={k}>{label}</Label>
                  <input id={k} type="number" min={0} max={max} value={gen[k]} onChange={(e) => setGen({ ...gen, [k]: Math.max(0, Math.min(max, Number(e.target.value))) })}
                    className="flex h-10 w-full rounded-lg border border-input bg-background/60 px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" />
                </div>
              ))}
            </div>
          </div>
          <DialogFooter><Button variant="outline" onClick={() => setGenOpen(false)}>Cancel</Button><Button variant="gradient" onClick={generate} loading={generating}>{generating ? "Generating…" : "Generate quiz"}</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
