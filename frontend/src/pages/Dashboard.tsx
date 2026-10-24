import { Link } from "react-router-dom";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis, Legend } from "recharts";
import { BookOpen, Brain, Clock, FileText, Layers, Plus, Sparkles, UploadCloud, Activity, CheckCircle2 } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Progress } from "@/components/ui/progress";
import { EmptyState, ErrorNote, ModeBadge, StatusBadge } from "@/components/common";
import { LectureRow } from "@/components/LectureCard";
import { useApi, useInterval } from "@/hooks/useApi";
import { useAuth } from "@/hooks/useAuth";
import { timeAgo } from "@/utils/format";
import type { ActivityDay, DashboardStats } from "@/types";

function Stat({ icon: Icon, label, value, hint, tone }: { icon: any; label: string; value: string | number; hint?: string; tone: string }) {
  return (
    <Card className="card-hover relative overflow-hidden">
      <div className={`absolute -right-6 -top-6 h-24 w-24 rounded-full opacity-20 blur-2xl ${tone}`} />
      <CardContent className="p-5">
        <div className="flex items-center justify-between">
          <span className="text-sm text-muted-foreground">{label}</span>
          <span className={`rounded-lg p-2 text-white ${tone}`}><Icon className="h-4 w-4" /></span>
        </div>
        <div className="mt-3 text-3xl font-bold tracking-tight">{value}</div>
        {hint && <div className="mt-1 text-xs text-muted-foreground">{hint}</div>}
      </CardContent>
    </Card>
  );
}

const KIND_ICON: Record<string, any> = { notes: FileText, quiz: Brain, flashcards: Layers, summary: Sparkles };
const KIND_TAB: Record<string, string> = { notes: "notes", quiz: "quiz", flashcards: "flashcards", summary: "summary" };

export default function Dashboard() {
  const { user } = useAuth();
  const stats = useApi<DashboardStats>("/api/dashboard/stats");
  const tz = -new Date().getTimezoneOffset();
  const activity = useApi<{ days: ActivityDay[] }>(`/api/dashboard/activity?days=7&tz_offset_minutes=${tz}`);
  const busy = (stats.data?.jobs || []).some((j) => j.status === "processing" || j.status === "queued");
  useInterval(() => stats.reload(true), 4000, busy);

  const s = stats.data;
  const hour = new Date().getHours();
  const greet = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-sm text-muted-foreground">{greet},</p>
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">{user?.name?.split(" ")[0]} 👋</h1>
          <p className="mt-1 text-sm text-muted-foreground">Here's what's happening with your lectures.</p>
        </div>
        <Button asChild variant="gradient" size="lg"><Link to="/app/upload"><Plus /> Upload lecture</Link></Button>
      </div>

      {stats.error && <ErrorNote message={stats.error.message} onRetry={() => stats.reload()} />}

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {!s ? (
          Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-[124px] rounded-2xl" />)
        ) : (
          <>
            <Stat icon={BookOpen} label="Lectures processed" value={s.completed_lectures} hint={`${s.total_lectures} uploaded`} tone="bg-indigo-500" />
            <Stat icon={Clock} label="Learning hours" value={s.learning_hours < 1 ? `${Math.round(s.learning_minutes)} min` : `${s.learning_hours} h`} hint="of processed lectures" tone="bg-violet-500" />
            <Stat icon={FileText} label="Notes generated" value={s.notes_count} hint="study note sets" tone="bg-fuchsia-500" />
            <Stat icon={Brain} label="Quizzes completed" value={s.quizzes_completed} hint={s.average_quiz_score != null ? `avg score ${s.average_quiz_score}%` : "no attempts yet"} tone="bg-sky-500" />
          </>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <div>
              <CardTitle className="flex items-center gap-2"><Activity className="h-4 w-4 text-primary" />Weekly study activity</CardTitle>
              <CardDescription>Study actions (quizzes, flashcard reviews, chat, note edits) and lecture minutes processed</CardDescription>
            </div>
          </CardHeader>
          <CardContent>
            {!activity.data ? (
              <Skeleton className="h-64" />
            ) : (
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={activity.data.days} margin={{ left: -20, right: 4, top: 8 }}>
                    <defs>
                      <linearGradient id="bar1" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#818cf8" /><stop offset="100%" stopColor="#6366f1" stopOpacity={0.6} /></linearGradient>
                      <linearGradient id="bar2" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#e879f9" /><stop offset="100%" stopColor="#a855f7" stopOpacity={0.6} /></linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                    <XAxis dataKey="label" tickLine={false} axisLine={false} fontSize={12} stroke="hsl(var(--muted-foreground))" />
                    <YAxis allowDecimals={false} tickLine={false} axisLine={false} fontSize={12} stroke="hsl(var(--muted-foreground))" />
                    <Tooltip cursor={{ fill: "hsl(var(--secondary))", opacity: 0.5 }} contentStyle={{ background: "hsl(var(--popover))", border: "1px solid hsl(var(--border))", borderRadius: 12, fontSize: 12 }} />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Bar dataKey="study_actions" name="Study actions" fill="url(#bar1)" radius={[6, 6, 0, 0]} maxBarSize={28} />
                    <Bar dataKey="minutes" name="Lecture minutes" fill="url(#bar2)" radius={[6, 6, 0, 0]} maxBarSize={28} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Processing jobs</CardTitle>
            <CardDescription>Live status of your uploads</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {!s ? (
              <Skeleton className="h-24" />
            ) : s.jobs.length === 0 ? (
              <div className="flex items-center gap-3 rounded-xl border border-dashed p-4 text-sm text-muted-foreground"><CheckCircle2 className="h-5 w-5 text-success" />All caught up. No jobs running.</div>
            ) : (
              s.jobs.map((j) => (
                <Link key={j.id} to={`/app/lectures/${j.id}`} className="block rounded-xl border p-3 transition-colors hover:bg-secondary/60">
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-sm font-medium">{j.title}</span>
                    <StatusBadge status={j.status} />
                  </div>
                  {j.status === "failed" ? (
                    <p className="mt-1.5 line-clamp-2 text-xs text-destructive">{j.error}</p>
                  ) : (
                    <>
                      <Progress value={j.progress} className="mt-2 h-1.5" />
                      <p className="mt-1 text-xs text-muted-foreground">{j.current_step_label || "Waiting in queue"} · {j.progress}%</p>
                    </>
                  )}
                </Link>
              ))
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <div>
              <CardTitle>Recent lectures</CardTitle>
              <CardDescription>Your latest uploads</CardDescription>
            </div>
            <Button asChild variant="ghost" size="sm"><Link to="/app/library">View all</Link></Button>
          </CardHeader>
          <CardContent className="space-y-1">
            {!s ? (
              Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-14" />)
            ) : s.recent_lectures.length === 0 ? (
              <EmptyState icon={<UploadCloud />} title="No lectures yet" description="Upload your first recording. We'll transcribe it and build notes, a quiz and flashcards automatically."
                action={<Button asChild variant="gradient"><Link to="/app/upload"><UploadCloud /> Upload a lecture</Link></Button>} />
            ) : (
              s.recent_lectures.map((l) => <LectureRow key={l.id} lecture={l} />)
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Recently generated</CardTitle>
            <CardDescription>Study materials ready to use</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {!s ? (
              <Skeleton className="h-32" />
            ) : s.recent_materials.length === 0 ? (
              <p className="text-sm text-muted-foreground">Materials appear here once a lecture finishes processing.</p>
            ) : (
              s.recent_materials.map((m, i) => {
                const Icon = KIND_ICON[m.kind] || FileText;
                return (
                  <Link key={i} to={`/app/lectures/${m.lecture_id}/${KIND_TAB[m.kind]}`} className="flex items-center gap-3 rounded-xl p-2 transition-colors hover:bg-secondary/60">
                    <span className="rounded-lg bg-primary/15 p-2 text-primary"><Icon className="h-4 w-4" /></span>
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-medium capitalize">{m.kind}</div>
                      <div className="truncate text-xs text-muted-foreground">{m.lecture_title} · {timeAgo(m.updated_at)}</div>
                    </div>
                    <ModeBadge mode={m.mode} />
                  </Link>
                );
              })
            )}
          </CardContent>
        </Card>
      </div>

      {activity.data && activity.data.days.some((d) => d.quiz_attempts || d.flashcard_reviews) && (
        <Card>
          <CardHeader><CardTitle>Revision breakdown</CardTitle><CardDescription>Quiz attempts and flashcard reviews this week</CardDescription></CardHeader>
          <CardContent className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={activity.data.days} margin={{ left: -20, right: 4 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                <XAxis dataKey="label" tickLine={false} axisLine={false} fontSize={12} stroke="hsl(var(--muted-foreground))" />
                <YAxis allowDecimals={false} tickLine={false} axisLine={false} fontSize={12} stroke="hsl(var(--muted-foreground))" />
                <Tooltip contentStyle={{ background: "hsl(var(--popover))", border: "1px solid hsl(var(--border))", borderRadius: 12, fontSize: 12 }} />
                <Area type="monotone" dataKey="flashcard_reviews" name="Flashcard reviews" stroke="#a855f7" fill="#a855f7" fillOpacity={0.2} />
                <Area type="monotone" dataKey="quiz_attempts" name="Quiz attempts" stroke="#6366f1" fill="#6366f1" fillOpacity={0.25} />
              </AreaChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
