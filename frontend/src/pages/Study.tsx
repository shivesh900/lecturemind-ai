import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { BarChart3, Brain, Target, Trophy, Layers } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { EmptyState, ErrorNote, PageHeader } from "@/components/common";
import { useApi } from "@/hooks/useApi";
import { formatDate, timeAgo } from "@/utils/format";
import { cn } from "@/utils/cn";
import type { ActivityDay, DashboardStats, QuizAttempt } from "@/types";

export default function Study() {
  const { data, error, loading, reload } = useApi<{ attempts: QuizAttempt[] }>("/api/attempts");
  const stats = useApi<DashboardStats>("/api/dashboard/stats");
  const tz = -new Date().getTimezoneOffset();
  const act = useApi<{ days: ActivityDay[] }>(`/api/dashboard/activity?days=30&tz_offset_minutes=${tz}`);
  const attempts = data?.attempts || [];
  const byLecture = Object.values(attempts.reduce<Record<string, { title: string; scores: number[] }>>((acc, a) => {
    (acc[a.lecture_id] ||= { title: a.lecture_title || "Lecture", scores: [] }).scores.push(a.score);
    return acc;
  }, {})).map((x) => ({ title: x.title.length > 22 ? x.title.slice(0, 21) + "…" : x.title, avg: Math.round(x.scores.reduce((a, b) => a + b, 0) / x.scores.length), best: Math.max(...x.scores) }));
  const trend = [...attempts].reverse().map((a, i) => ({ n: i + 1, score: a.score, date: formatDate(a.created_at) }));
  const avg = attempts.length ? Math.round(attempts.reduce((s, a) => s + a.score, 0) / attempts.length) : null;
  const best = attempts.length ? Math.max(...attempts.map((a) => a.score)) : null;

  return (
    <div>
      <PageHeader icon={<BarChart3 />} title="Study analytics" description="Your quiz performance and revision activity across all lectures." />
      {error && <ErrorNote message={error.message} onRetry={() => reload()} />}
      {loading ? <Skeleton className="h-64" /> : attempts.length === 0 ? (
        <EmptyState icon={<Brain />} title="No quiz attempts yet" description="Take a quiz in any lecture workspace and your scores and progress will show up here." action={<Button asChild><Link to="/app/library">Go to library</Link></Button>} />
      ) : (
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            {[[Brain, "Attempts", attempts.length], [Target, "Average score", `${avg}%`], [Trophy, "Best score", `${best}%`], [Layers, "Cards reviewed", stats.data?.flashcards_reviewed ?? "—"]].map(([Icon, label, val]: any) => (
              <Card key={label}><CardContent className="p-5"><div className="flex items-center gap-2 text-sm text-muted-foreground"><Icon className="h-4 w-4 text-primary" />{label}</div><div className="mt-2 text-3xl font-bold">{val}</div></CardContent></Card>
            ))}
          </div>
          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader><CardTitle>Score trend</CardTitle><CardDescription>Every attempt, oldest to newest</CardDescription></CardHeader>
              <CardContent className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={trend} margin={{ left: -20, right: 8, top: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                    <XAxis dataKey="n" fontSize={12} tickLine={false} axisLine={false} stroke="hsl(var(--muted-foreground))" />
                    <YAxis domain={[0, 100]} fontSize={12} tickLine={false} axisLine={false} stroke="hsl(var(--muted-foreground))" />
                    <Tooltip contentStyle={{ background: "hsl(var(--popover))", border: "1px solid hsl(var(--border))", borderRadius: 12, fontSize: 12 }} labelFormatter={(n) => `Attempt ${n}`} />
                    <Line type="monotone" dataKey="score" stroke="#8b5cf6" strokeWidth={2.5} dot={{ r: 3, fill: "#8b5cf6" }} />
                  </LineChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle>By lecture</CardTitle><CardDescription>Average vs best score</CardDescription></CardHeader>
              <CardContent className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={byLecture} margin={{ left: -20, right: 8, top: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                    <XAxis dataKey="title" fontSize={11} tickLine={false} axisLine={false} stroke="hsl(var(--muted-foreground))" />
                    <YAxis domain={[0, 100]} fontSize={12} tickLine={false} axisLine={false} stroke="hsl(var(--muted-foreground))" />
                    <Tooltip contentStyle={{ background: "hsl(var(--popover))", border: "1px solid hsl(var(--border))", borderRadius: 12, fontSize: 12 }} />
                    <Bar dataKey="avg" name="Average" fill="#6366f1" radius={[6, 6, 0, 0]} maxBarSize={32} />
                    <Bar dataKey="best" name="Best" fill="#a855f7" radius={[6, 6, 0, 0]} maxBarSize={32} />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </div>
          {act.data && (
            <Card>
              <CardHeader><CardTitle>Last 30 days</CardTitle><CardDescription>Study actions per day</CardDescription></CardHeader>
              <CardContent>
                <div className="grid grid-cols-10 gap-1.5 sm:grid-cols-15" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(22px, 1fr))" }}>
                  {act.data.days.map((d) => (
                    <div key={d.date} title={`${d.date}: ${d.study_actions} actions`} className={cn("aspect-square rounded-md", d.study_actions === 0 ? "bg-muted" : d.study_actions < 3 ? "bg-indigo-500/40" : d.study_actions < 8 ? "bg-indigo-500/70" : "bg-violet-500")} />
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
          <Card>
            <CardHeader><CardTitle>Recent attempts</CardTitle></CardHeader>
            <CardContent className="divide-y">
              {attempts.slice(0, 15).map((a) => (
                <Link key={a.id} to={`/app/lectures/${a.lecture_id}/quiz`} className="flex items-center justify-between gap-3 py-2.5 text-sm hover:text-primary">
                  <span className="truncate">{a.lecture_title}</span>
                  <span className="flex shrink-0 items-center gap-4"><span className="text-xs text-muted-foreground">{timeAgo(a.created_at)}</span>
                    <span className={cn("w-12 text-right font-semibold tabular-nums", a.score >= 80 ? "text-success" : a.score >= 50 ? "text-warning" : "text-destructive")}>{a.score}%</span></span>
                </Link>
              ))}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
