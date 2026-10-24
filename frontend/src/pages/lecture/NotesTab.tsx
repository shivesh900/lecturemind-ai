import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Copy, Download, Eye, NotebookPen, Pencil, RefreshCw, Save, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Textarea } from "@/components/ui/input";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Badge } from "@/components/ui/badge";
import { ErrorNote, ModeBadge } from "@/components/common";
import { Markdown } from "@/components/Markdown";
import { useApi } from "@/hooks/useApi";
import { ApiError, download, exportUrl, patch, post } from "@/services/api";
import { timeAgo } from "@/utils/format";
import type { NoteStyle, NotesDoc } from "@/types";
import { useWorkspace } from "./context";
import { NotReady, TabSkeleton } from "./shared";

export default function NotesTab() {
  const { lecture, reload: reloadLecture } = useWorkspace();
  const has = lecture.available?.notes;
  const { data, error, loading, reload, setData } = useApi<NotesDoc>(has ? `/api/lectures/${lecture.id}/notes` : null, [has, lecture.status]);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [regen, setRegen] = useState(false);
  useEffect(() => { if (data) setDraft(data.markdown); }, [data]);

  const save = async () => {
    setSaving(true);
    try { const d = await patch<NotesDoc>(`/api/lectures/${lecture.id}/notes`, { markdown: draft }); setData(d); setEditing(false); toast.success("Notes saved"); }
    catch (e) { toast.error((e as ApiError).message); } finally { setSaving(false); }
  };
  const regenerate = async (style: NoteStyle) => {
    if (data?.edited && !confirm("Regenerating replaces your edited notes. Continue?")) return;
    setRegen(true);
    try { await post(`/api/lectures/${lecture.id}/notes`, { style }); toast.success(`Regenerating ${style} notes…`); await reloadLecture(true); }
    catch (e) { toast.error((e as ApiError).message); } finally { setRegen(false); }
  };
  const dl = async (fmt: string) => {
    try { const n = await download(exportUrl(lecture.id, "notes", fmt), `notes.${fmt}`); toast.success(`Downloaded ${n}`); }
    catch (e) { toast.error((e as ApiError).message); }
  };

  if (!has || (lecture.status === "processing" && lecture.steps.notes?.status !== "completed"))
    return <NotReady lecture={lecture} what="notes" icon={<NotebookPen />} onGenerate={lecture.status === "completed" ? () => regenerate("exam") : undefined} generating={regen} />;
  if (error) return <ErrorNote message={error.message} onRetry={() => reload()} />;
  if (loading || !data) return <TabSkeleton />;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <ModeBadge mode={data.mode} />
          {data.edited && <Badge variant="secondary">Edited</Badge>}
          <span>Updated {timeAgo(data.updated_at)}</span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {editing ? (
            <>
              <Button size="sm" variant="outline" onClick={() => { setEditing(false); setDraft(data.markdown); }}><X />Cancel</Button>
              <Button size="sm" onClick={save} loading={saving}><Save />Save notes</Button>
            </>
          ) : (
            <Button size="sm" variant="outline" onClick={() => setEditing(true)}><Pencil />Edit</Button>
          )}
          <Button size="sm" variant="outline" onClick={async () => { await navigator.clipboard.writeText(data.markdown); toast.success("Notes copied (Markdown)"); }}><Copy />Copy</Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild><Button size="sm" variant="outline"><Download />Export</Button></DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => dl("pdf")}>PDF</DropdownMenuItem>
              <DropdownMenuItem onClick={() => dl("docx")}>Word (DOCX)</DropdownMenuItem>
              <DropdownMenuItem onClick={() => dl("md")}>Markdown (.md)</DropdownMenuItem>
              <DropdownMenuItem onClick={() => dl("txt")}>Plain text (.txt)</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          <DropdownMenu>
            <DropdownMenuTrigger asChild><Button size="sm" variant="ghost" disabled={lecture.status !== "completed"} loading={regen}><RefreshCw />Regenerate</Button></DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel>Note style</DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => regenerate("exam")}>Exam-focused</DropdownMenuItem>
              <DropdownMenuItem onClick={() => regenerate("concise")}>Concise</DropdownMenuItem>
              <DropdownMenuItem onClick={() => regenerate("detailed")}>Detailed</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      {editing ? (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card className="p-2"><Textarea value={draft} onChange={(e) => setDraft(e.target.value)} className="min-h-[60vh] border-0 bg-transparent font-mono text-[13px] leading-6 focus-visible:ring-0" aria-label="Notes markdown editor" /></Card>
          <Card className="hidden max-h-[70vh] overflow-auto p-6 lg:block"><div className="mb-3 flex items-center gap-1.5 text-xs text-muted-foreground"><Eye className="h-3.5 w-3.5" />Live preview</div><Markdown>{draft}</Markdown></Card>
        </div>
      ) : (
        <Card className="p-6 sm:p-8"><Markdown>{data.markdown}</Markdown></Card>
      )}
    </div>
  );
}
