import { useEffect, useRef, useState, type FormEvent } from "react";
import { toast } from "sonner";
import { Bot, Loader2, MessagesSquare, SendHorizonal, Trash2, User, AlertCircle, Quote } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Textarea } from "@/components/ui/input";
import { ErrorNote } from "@/components/common";
import { Markdown } from "@/components/Markdown";
import { useApi } from "@/hooks/useApi";
import { useSystemStatus } from "@/hooks/useSystemStatus";
import { ApiError, del, post } from "@/services/api";
import { cn } from "@/utils/cn";
import type { ChatMessage } from "@/types";
import { useWorkspace } from "./context";
import { NotReady, TabSkeleton, TimeChip } from "./shared";

const SUGGESTIONS = ["Summarize this lecture in simple words", "What are the key definitions?", "Explain the hardest concept with an example", "Where was the main formula discussed?"];

export default function ChatTab() {
  const { lecture, jumpTo } = useWorkspace();
  const { status } = useSystemStatus();
  const ready = lecture.steps?.process_transcript?.status === "completed";
  const { data, error, loading, reload, setData } = useApi<{ messages: ChatMessage[] }>(ready ? `/api/lectures/${lecture.id}/chat` : null, [ready]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const messages = data?.messages || [];
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [messages.length, sending]);

  if (!ready) return <NotReady lecture={lecture} what="chat" icon={<MessagesSquare />} />;
  if (error) return <ErrorNote message={error.message} onRetry={() => reload()} />;
  if (loading || !data) return <TabSkeleton />;

  const send = async (text: string) => {
    const msg = text.trim();
    if (!msg || sending) return;
    setInput("");
    const optimistic: ChatMessage = { id: "tmp", role: "user", content: msg, created_at: new Date().toISOString() };
    setData({ messages: [...messages, optimistic] });
    setSending(true);
    try {
      const r = await post<{ user_message: ChatMessage; message: ChatMessage }>(`/api/lectures/${lecture.id}/chat`, { message: msg });
      setData({ messages: [...messages, r.user_message, r.message] });
    } catch (e) {
      setData({ messages });
      setInput(msg);
      toast.error((e as ApiError).message);
    } finally { setSending(false); }
  };
  const onSubmit = (e: FormEvent) => { e.preventDefault(); send(input); };
  const clear = async () => {
    try { await del(`/api/lectures/${lecture.id}/chat`); setData({ messages: [] }); toast.success("Chat cleared"); }
    catch (e) { toast.error((e as ApiError).message); }
  };

  return (
    <Card className="flex h-[calc(100vh-330px)] min-h-[480px] flex-col overflow-hidden">
      <div className="flex items-center justify-between border-b px-4 py-3">
        <div className="flex items-center gap-2.5">
          <span className="rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 p-1.5 text-white"><Bot className="h-4 w-4" /></span>
          <div>
            <div className="text-sm font-semibold">Lecture assistant</div>
            <div className="text-xs text-muted-foreground">{status?.ai_enabled ? "Answers only from this lecture, with timestamps" : "Demo mode: shows the most relevant passages (no AI answers)"}</div>
          </div>
        </div>
        {messages.length > 0 && <Button size="sm" variant="ghost" onClick={clear}><Trash2 />Clear</Button>}
      </div>

      <div className="flex-1 space-y-5 overflow-y-auto p-4 sm:p-6" aria-live="polite">
        {messages.length === 0 && (
          <div className="mx-auto flex max-w-lg flex-col items-center pt-6 text-center">
            <div className="mb-4 rounded-2xl bg-gradient-to-br from-indigo-500/20 to-violet-500/20 p-4 text-primary"><MessagesSquare className="h-7 w-7" /></div>
            <h3 className="font-semibold">Ask anything about “{lecture.title}”</h3>
            <p className="mt-1 text-sm text-muted-foreground">Answers are grounded in the transcript. If the lecture doesn't cover something, the assistant will say so.</p>
            <div className="mt-5 grid w-full gap-2 sm:grid-cols-2">
              {SUGGESTIONS.map((s) => <button key={s} onClick={() => send(s)} className="rounded-xl border bg-card px-3 py-2.5 text-left text-sm transition-colors hover:border-primary/50 hover:bg-secondary/60">{s}</button>)}
            </div>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={m.id + i} className={cn("flex gap-3", m.role === "user" && "flex-row-reverse")}>
            <span className={cn("flex h-8 w-8 shrink-0 items-center justify-center rounded-full", m.role === "user" ? "bg-secondary" : "bg-gradient-to-br from-indigo-500 to-violet-600 text-white")}>
              {m.role === "user" ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
            </span>
            <div className={cn("max-w-[85%] space-y-2", m.role === "user" && "items-end")}>
              <div className={cn("rounded-2xl px-4 py-2.5 text-sm", m.role === "user" ? "rounded-tr-sm bg-primary text-primary-foreground" : "rounded-tl-sm border bg-card")}>
                {m.role === "assistant" && m.supported === false && <div className="mb-1 flex items-center gap-1.5 text-xs font-medium text-warning"><AlertCircle className="h-3.5 w-3.5" />Not covered in this lecture</div>}
                {m.role === "assistant" ? <Markdown className="[&_p]:my-1 [&_p]:text-sm [&_li]:text-sm [&_li]:leading-6">{m.content}</Markdown> : <p className="whitespace-pre-wrap">{m.content}</p>}
              </div>
              {m.citations && m.citations.length > 0 && (
                <div className="space-y-1.5">
                  <div className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Sources</div>
                  {m.citations.map((c, j) => (
                    <button key={j} onClick={() => jumpTo(c.timestamp)} className="flex w-full items-start gap-2 rounded-xl border bg-secondary/40 p-2.5 text-left text-xs transition-colors hover:border-primary/40">
                      <TimeChip t={c.timestamp} />
                      <Quote className="mt-0.5 h-3 w-3 shrink-0 text-muted-foreground" />
                      <span className="line-clamp-2 text-muted-foreground">{c.excerpt}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        {sending && (
          <div className="flex gap-3">
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500 to-violet-600 text-white"><Bot className="h-4 w-4" /></span>
            <div className="flex items-center gap-2 rounded-2xl rounded-tl-sm border bg-card px-4 py-3 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" />Searching the lecture…</div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      <form onSubmit={onSubmit} className="border-t p-3">
        <div className="flex items-end gap-2">
          <Textarea value={input} onChange={(e) => setInput(e.target.value)} placeholder="Ask about a concept, formula, example or section…" rows={1} maxLength={2000}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input); } }}
            className="max-h-32 min-h-[44px] resize-none" aria-label="Your question" />
          <Button type="submit" size="icon" className="h-11 w-11 shrink-0" disabled={!input.trim() || sending} aria-label="Send"><SendHorizonal /></Button>
        </div>
      </form>
    </Card>
  );
}
