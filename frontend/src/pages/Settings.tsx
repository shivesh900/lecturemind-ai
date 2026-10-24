import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { AlertTriangle, CheckCircle2, KeyRound, Monitor, Moon, Palette, Server, Settings as SettingsIcon, Sun, Trash2, User, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ConfirmDialog, PageHeader } from "@/components/common";
import { useAuth } from "@/hooks/useAuth";
import { useTheme } from "@/hooks/useTheme";
import { useSystemStatus } from "@/hooks/useSystemStatus";
import { ApiError, del, patch, post } from "@/services/api";
import { LANGUAGES } from "@/utils/format";
import { cn } from "@/utils/cn";
import type { NoteStyle, Theme, User as UserT } from "@/types";

function Row({ ok, label, value }: { ok: boolean; label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-lg bg-secondary/50 px-3 py-2 text-sm">
      <span className="flex items-center gap-2">{ok ? <CheckCircle2 className="h-4 w-4 text-success" /> : <XCircle className="h-4 w-4 text-warning" />}{label}</span>
      <span className="truncate text-right text-muted-foreground">{value}</span>
    </div>
  );
}

export default function Settings() {
  const { user, setUser, logout } = useAuth();
  const { theme, setTheme } = useTheme();
  const { status } = useSystemStatus();
  const nav = useNavigate();
  const [name, setName] = useState(user?.name || "");
  const [lang, setLang] = useState(user?.preferences.default_language || "auto");
  const [style, setStyle] = useState<NoteStyle>(user?.preferences.note_style || "exam");
  const [saving, setSaving] = useState(false);
  const [pw, setPw] = useState({ current: "", next: "" });
  const [pwBusy, setPwBusy] = useState(false);
  const [wipeOpen, setWipeOpen] = useState(false);
  const [wipeBusy, setWipeBusy] = useState(false);
  const [delOpen, setDelOpen] = useState(false);
  const [delPw, setDelPw] = useState("");
  const [delBusy, setDelBusy] = useState(false);

  const saveProfile = async (t: Theme = theme) => {
    setSaving(true);
    try {
      const r = await patch<{ user: UserT }>("/api/users/me", { name: name.trim(), preferences: { theme: t, default_language: lang, note_style: style } });
      setUser(r.user);
      toast.success("Settings saved");
    } catch (e) { toast.error((e as ApiError).message); } finally { setSaving(false); }
  };
  const changePw = async () => {
    if (pw.next.length < 8) return toast.error("New password must be at least 8 characters.");
    setPwBusy(true);
    try { await post("/api/users/me/password", { current_password: pw.current, new_password: pw.next }); toast.success("Password changed. Please sign in again."); await logout(); nav("/login"); }
    catch (e) { toast.error((e as ApiError).message); } finally { setPwBusy(false); }
  };
  const wipe = async () => {
    setWipeBusy(true);
    try { await del("/api/users/me/data"); toast.success("All lectures and study data deleted"); setWipeOpen(false); }
    catch (e) { toast.error((e as ApiError).message); } finally { setWipeBusy(false); }
  };
  const deleteAccount = async () => {
    setDelBusy(true);
    try { await del("/api/users/me", { password: delPw }); setUser(null); toast.success("Account deleted"); nav("/"); }
    catch (e) { toast.error((e as ApiError).message); } finally { setDelBusy(false); }
  };

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <PageHeader icon={<SettingsIcon />} title="Settings" description="Profile, preferences, data controls and AI configuration." />

      <Card>
        <CardHeader><CardTitle className="flex items-center gap-2"><User className="h-4 w-4 text-primary" />Profile & preferences</CardTitle></CardHeader>
        <CardContent className="space-y-5">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5"><Label htmlFor="name">Name</Label><Input id="name" value={name} onChange={(e) => setName(e.target.value)} maxLength={80} /></div>
            <div className="space-y-1.5"><Label htmlFor="email">Email</Label><Input id="email" value={user?.email || ""} disabled /></div>
            <div className="space-y-1.5">
              <Label>Default transcription language</Label>
              <Select value={lang} onValueChange={setLang}><SelectTrigger aria-label="Default language"><SelectValue /></SelectTrigger>
                <SelectContent>{LANGUAGES.map((l) => <SelectItem key={l.code} value={l.code}>{l.name}</SelectItem>)}</SelectContent></Select>
            </div>
            <div className="space-y-1.5">
              <Label>Default note style</Label>
              <Select value={style} onValueChange={(v) => setStyle(v as NoteStyle)}><SelectTrigger aria-label="Note style"><SelectValue /></SelectTrigger>
                <SelectContent><SelectItem value="exam">Exam-focused</SelectItem><SelectItem value="concise">Concise</SelectItem><SelectItem value="detailed">Detailed</SelectItem></SelectContent></Select>
            </div>
          </div>
          <div className="space-y-2">
            <Label className="flex items-center gap-2"><Palette className="h-4 w-4" />Theme</Label>
            <div className="grid grid-cols-3 gap-2 sm:max-w-md">
              {([["light", Sun, "Light"], ["dark", Moon, "Dark"], ["system", Monitor, "System"]] as const).map(([t, I, l]) => (
                <button key={t} onClick={() => setTheme(t)} className={cn("flex flex-col items-center gap-1.5 rounded-xl border p-3 text-sm transition-all", theme === t ? "border-primary bg-primary/10 ring-1 ring-primary" : "hover:bg-secondary")} aria-pressed={theme === t}>
                  <I className="h-5 w-5" />{l}
                </button>
              ))}
            </div>
          </div>
          <Button onClick={() => saveProfile()} loading={saving}>Save preferences</Button>
        </CardContent>
      </Card>

      <Card id="ai" className="scroll-mt-24">
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><Server className="h-4 w-4 text-primary" />AI & system configuration</CardTitle>
          <CardDescription>Read-only status. Secrets live only in the server's .env file and are never sent to the browser.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {status ? (
            <div className="grid gap-2 sm:grid-cols-2">
              <Row ok={status.ai_enabled} label="AI generation" value={status.ai_enabled ? status.chat_model || "enabled" : "Demo mode (no key)"} />
              <Row ok={status.ai_enabled} label="Embeddings / semantic search" value={status.embedding_model || "off"} />
              <Row ok label="Transcription" value={`${status.transcription_provider} · ${status.transcription_model}`} />
              <Row ok={status.ffmpeg_available} label="FFmpeg" value={status.ffmpeg_available ? "installed" : "missing"} />
              <Row ok={status.database_ok} label="MongoDB" value={status.database_ok ? "connected" : "unreachable"} />
              <Row ok label="Upload limit" value={`${status.max_upload_mb} MB`} />
            </div>
          ) : <p className="text-sm text-muted-foreground">Loading…</p>}
          <div className="rounded-xl border border-primary/25 bg-primary/5 p-4 text-sm"><strong>Data handling:</strong> {status?.data_disclosure}</div>
          <details className="rounded-xl border p-4 text-sm">
            <summary className="cursor-pointer font-medium">Administrator setup instructions</summary>
            <ol className="mt-3 list-decimal space-y-2 pl-5 text-muted-foreground">
              <li>Copy <code className="rounded bg-muted px-1">.env.example</code> to <code className="rounded bg-muted px-1">.env</code> in the project root.</li>
              <li>Set <code className="rounded bg-muted px-1">OPENAI_API_KEY</code> to enable AI summaries, notes, quizzes, flashcards, knowledge maps, chat and semantic search. Optionally set <code className="rounded bg-muted px-1">OPENAI_CHAT_MODEL</code> and <code className="rounded bg-muted px-1">OPENAI_EMBEDDING_MODEL</code>.</li>
              <li>Choose transcription with <code className="rounded bg-muted px-1">TRANSCRIPTION_PROVIDER</code>: <em>local</em> (faster-whisper, free, private), <em>openai</em> (Whisper API) or <em>auto</em>. Pick the local model size with <code className="rounded bg-muted px-1">WHISPER_MODEL</code> (tiny/base/small/medium).</li>
              <li>Set <code className="rounded bg-muted px-1">MONGODB_URI</code> (local or Atlas) and a long random <code className="rounded bg-muted px-1">JWT_SECRET</code>.</li>
              <li>Restart the backend. This page will show the new status.</li>
            </ol>
          </details>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="flex items-center gap-2"><KeyRound className="h-4 w-4 text-primary" />Account security</CardTitle></CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
          <div className="space-y-1.5"><Label htmlFor="cur">Current password</Label><Input id="cur" type="password" autoComplete="current-password" value={pw.current} onChange={(e) => setPw({ ...pw, current: e.target.value })} /></div>
          <div className="space-y-1.5"><Label htmlFor="new">New password</Label><Input id="new" type="password" autoComplete="new-password" value={pw.next} onChange={(e) => setPw({ ...pw, next: e.target.value })} /></div>
          <Button variant="outline" onClick={changePw} loading={pwBusy} disabled={!pw.current || !pw.next}>Change password</Button>
        </CardContent>
      </Card>

      <Card className="border-destructive/30">
        <CardHeader><CardTitle className="flex items-center gap-2 text-destructive"><AlertTriangle className="h-4 w-4" />Data deletion</CardTitle><CardDescription>These actions are permanent.</CardDescription></CardHeader>
        <CardContent className="flex flex-col gap-3 sm:flex-row">
          <Button variant="outline" className="border-destructive/40 text-destructive hover:bg-destructive/10" onClick={() => setWipeOpen(true)}><Trash2 />Delete all my lectures & data</Button>
          <Button variant="destructive" onClick={() => setDelOpen(true)}><Trash2 />Delete my account</Button>
        </CardContent>
      </Card>

      <ConfirmDialog open={wipeOpen} onOpenChange={setWipeOpen} title="Delete all lectures and study data?" destructive confirmLabel="Delete everything" loading={wipeBusy} onConfirm={wipe}
        description="All uploads, transcripts, notes, quizzes, flashcards, chat history and audio files will be permanently deleted. Your account stays." />
      <Dialog open={delOpen} onOpenChange={setDelOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Delete your account?</DialogTitle><DialogDescription>This deletes your account and every lecture and file in it. Enter your password to confirm.</DialogDescription></DialogHeader>
          <Input type="password" placeholder="Password" value={delPw} onChange={(e) => setDelPw(e.target.value)} aria-label="Password" />
          <DialogFooter><Button variant="outline" onClick={() => setDelOpen(false)}>Cancel</Button><Button variant="destructive" onClick={deleteAccount} loading={delBusy} disabled={!delPw}>Delete account</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
