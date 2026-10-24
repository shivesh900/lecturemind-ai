import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { BookOpen, Clock, FileAudio, FileVideo, MoreVertical, Pencil, RefreshCw, Search, Trash2, UploadCloud, FileText, MessagesSquare, Filter } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input, Textarea } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { ConfirmDialog, EmptyState, ErrorNote, ModeBadge, PageHeader, StatusBadge } from "@/components/common";
import { useApi, useInterval } from "@/hooks/useApi";
import { ApiError, del, patch, post } from "@/services/api";
import { formatDate, formatDuration } from "@/utils/format";
import type { Lecture } from "@/types";

export default function Library() {
  const nav = useNavigate();
  const [q, setQ] = useState("");
  const [debounced, setDebounced] = useState("");
  const [subject, setSubject] = useState("all");
  const [status, setStatus] = useState("all");
  const [sort, setSort] = useState("newest");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  useEffect(() => { const t = setTimeout(() => setDebounced(q), 300); return () => clearTimeout(t); }, [q]);

  const params = new URLSearchParams({ sort });
  if (debounced) params.set("q", debounced);
  if (subject !== "all") params.set("subject", subject);
  if (status !== "all") params.set("status", status);
  if (from) params.set("date_from", from);
  if (to) params.set("date_to", to);
  const { data, error, loading, reload } = useApi<{ items: Lecture[]; subjects: string[] }>(`/api/lectures?${params}`);
  const busy = (data?.items || []).some((l) => l.status === "processing" || l.status === "queued");
  useInterval(() => reload(true), 4000, busy);

  const [editing, setEditing] = useState<Lecture | null>(null);
  const [form, setForm] = useState({ title: "", subject: "", description: "" });
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState<Lecture | null>(null);
  const [delBusy, setDelBusy] = useState(false);

  const openEdit = (l: Lecture) => { setEditing(l); setForm({ title: l.title, subject: l.subject || "", description: l.description || "" }); };
  const save = async () => {
    if (!editing) return;
    if (!form.title.trim()) return toast.error("Title can't be empty.");
    setSaving(true);
    try {
      await patch(`/api/lectures/${editing.id}`, form);
      toast.success("Lecture updated");
      setEditing(null);
      reload(true);
    } catch (e) { toast.error((e as ApiError).message); } finally { setSaving(false); }
  };
  const remove = async () => {
    if (!deleting) return;
    setDelBusy(true);
    try {
      await del(`/api/lectures/${deleting.id}`);
      toast.success(`Deleted "${deleting.title}"`);
      setDeleting(null);
      reload(true);
    } catch (e) { toast.error((e as ApiError).message); } finally { setDelBusy(false); }
  };
  const reprocess = async (l: Lecture) => {
    try {
      await post(`/api/lectures/${l.id}/reprocess`);
      toast.success("Reprocessing started");
      reload(true);
    } catch (e) { toast.error((e as ApiError).message); }
  };

  const items = data?.items || [];
  const filtered = !!(debounced || subject !== "all" || status !== "all" || from || to);

  return (
    <div>
      <PageHeader icon={<BookOpen />} title="Lecture library" description={data ? `${items.length} lecture${items.length === 1 ? "" : "s"}` : "All your uploaded lectures"}
        actions={<Button asChild variant="gradient"><Link to="/app/upload"><UploadCloud /> Upload</Link></Button>} />

      <Card className="mb-5 p-3">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by title, subject or description" className="pl-9" aria-label="Search lectures" />
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-5 lg:flex">
            <Select value={subject} onValueChange={setSubject}>
              <SelectTrigger className="lg:w-40" aria-label="Filter by subject"><SelectValue placeholder="Subject" /></SelectTrigger>
              <SelectContent><SelectItem value="all">All subjects</SelectItem>{(data?.subjects || []).map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
            </Select>
            <Select value={status} onValueChange={setStatus}>
              <SelectTrigger className="lg:w-36" aria-label="Filter by status"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All statuses</SelectItem><SelectItem value="completed">Ready</SelectItem><SelectItem value="processing">Processing</SelectItem>
                <SelectItem value="queued">Queued</SelectItem><SelectItem value="failed">Failed</SelectItem>
              </SelectContent>
            </Select>
            <Input type="date" value={from} onChange={(e) => setFrom(e.target.value)} aria-label="From date" className="lg:w-40" />
            <Input type="date" value={to} onChange={(e) => setTo(e.target.value)} aria-label="To date" className="lg:w-40" />
            <Select value={sort} onValueChange={setSort}>
              <SelectTrigger className="col-span-2 sm:col-span-1 lg:w-32" aria-label="Sort"><SelectValue /></SelectTrigger>
              <SelectContent><SelectItem value="newest">Newest</SelectItem><SelectItem value="oldest">Oldest</SelectItem><SelectItem value="title">Title A–Z</SelectItem></SelectContent>
            </Select>
          </div>
        </div>
      </Card>

      {error && <ErrorNote message={error.message} onRetry={() => reload()} />}
      {loading && !data ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-44 rounded-2xl" />)}</div>
      ) : items.length === 0 ? (
        filtered ? (
          <EmptyState icon={<Filter />} title="No lectures match these filters" action={<Button variant="outline" onClick={() => { setQ(""); setSubject("all"); setStatus("all"); setFrom(""); setTo(""); }}>Clear filters</Button>} />
        ) : (
          <EmptyState icon={<UploadCloud />} title="Your library is empty" description="Upload a lecture recording to get a transcript, summary, notes, quiz and flashcards."
            action={<Button asChild variant="gradient"><Link to="/app/upload">Upload your first lecture</Link></Button>} />
        )
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {items.map((l) => {
            const Icon = l.kind === "video" ? FileVideo : FileAudio;
            const busyL = l.status === "processing" || l.status === "queued";
            return (
              <Card key={l.id} className="card-hover group flex flex-col p-4">
                <div className="flex items-start gap-3">
                  <span className="rounded-xl bg-gradient-to-br from-indigo-500/20 to-violet-500/20 p-2.5 text-primary"><Icon className="h-5 w-5" /></span>
                  <div className="min-w-0 flex-1">
                    <Link to={`/app/lectures/${l.id}`} className="line-clamp-2 font-semibold leading-snug hover:text-primary">{l.title}</Link>
                    <p className="mt-0.5 truncate text-xs text-muted-foreground">{l.subject || "No subject"}</p>
                  </div>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild><Button variant="ghost" size="icon" className="-mr-2 -mt-1 h-8 w-8" aria-label={`Actions for ${l.title}`}><MoreVertical /></Button></DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => openEdit(l)}><Pencil />Rename / edit details</DropdownMenuItem>
                      <DropdownMenuItem disabled={l.status !== "completed"} onClick={() => nav(`/app/lectures/${l.id}/summary`)}><FileText />View summary</DropdownMenuItem>
                      <DropdownMenuItem disabled={l.status !== "completed"} onClick={() => nav(`/app/lectures/${l.id}/notes`)}><BookOpen />View notes</DropdownMenuItem>
                      <DropdownMenuItem disabled={l.status !== "completed"} onClick={() => nav(`/app/lectures/${l.id}/chat`)}><MessagesSquare />Ask the lecture</DropdownMenuItem>
                      <DropdownMenuItem disabled={busyL} onClick={() => reprocess(l)}><RefreshCw />{l.status === "failed" ? "Retry processing" : "Regenerate materials"}</DropdownMenuItem>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem onClick={() => setDeleting(l)} className="text-destructive focus:text-destructive"><Trash2 />Delete</DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
                {l.description && <p className="mt-3 line-clamp-2 text-sm text-muted-foreground">{l.description}</p>}
                <div className="mt-auto pt-4">
                  {busyL && <div className="mb-3"><Progress value={l.progress} className="h-1.5" /><p className="mt-1 text-xs text-muted-foreground">{l.current_step_label || "Queued"} · {l.progress}%</p></div>}
                  {l.status === "failed" && <p className="mb-3 line-clamp-2 text-xs text-destructive">{l.error}</p>}
                  <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                    <StatusBadge status={l.status} />
                    {l.status === "completed" && <ModeBadge mode={l.mode} />}
                    <span className="inline-flex items-center gap-1"><Clock className="h-3 w-3" />{formatDuration(l.duration)}</span>
                    <span className="ml-auto">{formatDate(l.created_at)}</span>
                  </div>
                  {l.status === "failed" && <Button size="sm" variant="outline" className="mt-3 w-full" onClick={() => reprocess(l)}><RefreshCw />Reprocess</Button>}
                </div>
              </Card>
            );
          })}
        </div>
      )}

      <Dialog open={!!editing} onOpenChange={(o) => !o && setEditing(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle>Edit lecture details</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1.5"><Label htmlFor="e-title">Title</Label><Input id="e-title" value={form.title} maxLength={200} onChange={(e) => setForm({ ...form, title: e.target.value })} /></div>
            <div className="space-y-1.5"><Label htmlFor="e-subject">Subject</Label><Input id="e-subject" value={form.subject} maxLength={100} onChange={(e) => setForm({ ...form, subject: e.target.value })} /></div>
            <div className="space-y-1.5"><Label htmlFor="e-desc">Description</Label><Textarea id="e-desc" value={form.description} maxLength={2000} onChange={(e) => setForm({ ...form, description: e.target.value })} /></div>
          </div>
          <DialogFooter><Button variant="outline" onClick={() => setEditing(null)}>Cancel</Button><Button onClick={save} loading={saving}>Save changes</Button></DialogFooter>
        </DialogContent>
      </Dialog>
      <ConfirmDialog open={!!deleting} onOpenChange={(o) => !o && setDeleting(null)} title="Delete this lecture?" destructive confirmLabel="Delete permanently" loading={delBusy} onConfirm={remove}
        description={<>“{deleting?.title}” and its transcript, notes, quizzes, flashcards, chat history and audio will be permanently deleted.</>} />
    </div>
  );
}
