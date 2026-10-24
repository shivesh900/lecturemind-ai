import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { ChevronLeft, ChevronRight, Download, Layers, RefreshCw, RotateCw, Shuffle, Eye, ListFilter } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { ErrorNote, ModeBadge } from "@/components/common";
import { useApi } from "@/hooks/useApi";
import { ApiError, download, exportUrl, post } from "@/services/api";
import { cn } from "@/utils/cn";
import type { Difficulty, Flashcard, FlashcardSet } from "@/types";
import { useWorkspace } from "./context";
import { NotReady, TabSkeleton } from "./shared";

type Mode = "all" | "review" | "hard";

export default function FlashcardsTab() {
  const { lecture } = useWorkspace();
  const has = lecture.available?.flashcards;
  const { data, error, loading, reload, setData } = useApi<FlashcardSet>(has ? `/api/lectures/${lecture.id}/flashcards` : null, [has, lecture.status]);
  const [order, setOrder] = useState<string[]>([]);
  const [pos, setPos] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [mode, setMode] = useState<Mode>("all");
  const [regen, setRegen] = useState(false);

  const cards = data?.cards || [];
  const deck = useMemo(() => {
    const byId = Object.fromEntries(cards.map((c) => [c.id, c]));
    const ids = (order.length ? order : cards.map((c) => c.id)).filter((id) => byId[id]);
    const list = ids.map((id) => byId[id]);
    if (mode === "review") return list.filter((c) => c.rating !== "easy");
    if (mode === "hard") return list.filter((c) => c.rating === "hard");
    return list;
  }, [cards, order, mode]);
  useEffect(() => { setPos(0); setFlipped(false); }, [mode]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.tagName === "INPUT" || (e.target as HTMLElement)?.tagName === "TEXTAREA") return;
      if (e.key === "ArrowRight") next();
      if (e.key === "ArrowLeft") prev();
      if (e.key === "Enter" || e.key.toLowerCase() === "f") setFlipped((f) => !f);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  if (!has || (lecture.status === "processing" && lecture.steps.flashcards?.status !== "completed"))
    return <NotReady lecture={lecture} what="flashcards" icon={<Layers />} />;
  if (error) return <ErrorNote message={error.message} onRetry={() => reload()} />;
  if (loading || !data) return <TabSkeleton />;

  const card: Flashcard | undefined = deck[Math.min(pos, deck.length - 1)];
  const reviewed = cards.filter((c) => c.review_count > 0).length;
  const counts = { easy: cards.filter((c) => c.rating === "easy").length, medium: cards.filter((c) => c.rating === "medium").length, hard: cards.filter((c) => c.rating === "hard").length };

  function next() { setFlipped(false); setPos((p) => (deck.length ? (p + 1) % deck.length : 0)); }
  function prev() { setFlipped(false); setPos((p) => (deck.length ? (p - 1 + deck.length) % deck.length : 0)); }
  const shuffle = () => {
    const ids = cards.map((c) => c.id);
    for (let i = ids.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [ids[i], ids[j]] = [ids[j], ids[i]]; }
    setOrder(ids); setPos(0); setFlipped(false); toast.success("Deck shuffled");
  };
  const rate = async (rating: Difficulty) => {
    if (!card) return;
    try {
      const r = await post<{ card: Flashcard }>(`/api/lectures/${lecture.id}/flashcards/${card.id}/review`, { rating });
      setData({ ...data, cards: cards.map((c) => (c.id === card.id ? r.card : c)) });
      next();
    } catch (e) { toast.error((e as ApiError).message); }
  };
  const regenerate = async () => {
    if (!confirm("Generate a fresh set of flashcards? Your ratings for the current set will be lost.")) return;
    setRegen(true);
    try { const d = await post<FlashcardSet>(`/api/lectures/${lecture.id}/flashcards`); setData(d); setOrder([]); setPos(0); toast.success(`${d.cards.length} new flashcards`); }
    catch (e) { toast.error((e as ApiError).message); } finally { setRegen(false); }
  };
  const exportCsv = async () => {
    try { const n = await download(exportUrl(lecture.id, "flashcards"), "flashcards.csv"); toast.success(`Downloaded ${n}`); }
    catch (e) { toast.error((e as ApiError).message); }
  };

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Tabs value={mode} onValueChange={(v) => setMode(v as Mode)}>
          <TabsList>
            <TabsTrigger value="all"><Layers />All ({cards.length})</TabsTrigger>
            <TabsTrigger value="review"><Eye />Review ({cards.filter((c) => c.rating !== "easy").length})</TabsTrigger>
            <TabsTrigger value="hard"><ListFilter />Hard ({counts.hard})</TabsTrigger>
          </TabsList>
        </Tabs>
        <div className="flex flex-wrap items-center gap-2">
          <ModeBadge mode={data.mode} />
          <Button size="sm" variant="outline" onClick={shuffle}><Shuffle />Shuffle</Button>
          <Button size="sm" variant="outline" onClick={exportCsv}><Download />CSV</Button>
          <Button size="sm" variant="ghost" onClick={regenerate} loading={regen} disabled={lecture.status !== "completed"}><RefreshCw />New set</Button>
        </div>
      </div>

      <Card className="p-4">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2 text-sm">
          <span className="font-medium">{reviewed} of {cards.length} cards reviewed</span>
          <div className="flex gap-1.5"><Badge variant="success">Easy {counts.easy}</Badge><Badge variant="warning">Medium {counts.medium}</Badge><Badge variant="destructive">Hard {counts.hard}</Badge></div>
        </div>
        <Progress value={cards.length ? (reviewed / cards.length) * 100 : 0} className="h-1.5" />
      </Card>

      {!card ? (
        <Card className="p-12 text-center">
          <p className="font-medium">{mode === "hard" ? "No cards marked Hard. Nice!" : "Everything here is marked Easy 🎉"}</p>
          <Button className="mt-4" variant="outline" onClick={() => setMode("all")}>Show all cards</Button>
        </Card>
      ) : (
        <>
          <div className="text-center text-sm tabular-nums text-muted-foreground">Card {Math.min(pos, deck.length - 1) + 1} / {deck.length}</div>
          <div className="[perspective:1400px]">
            <button type="button" onClick={() => setFlipped((f) => !f)} aria-label={flipped ? "Show question" : "Show answer"}
              className={cn("relative block h-72 w-full transition-transform duration-500 [transform-style:preserve-3d] sm:h-80", flipped && "[transform:rotateY(180deg)]")}>
              <Card className="absolute inset-0 flex flex-col items-center justify-center p-8 text-center [backface-visibility:hidden]">
                <div className="absolute left-5 top-5 text-xs font-semibold uppercase tracking-wider text-primary">Question</div>
                {card.rating && <Badge variant={card.rating === "easy" ? "success" : card.rating === "medium" ? "warning" : "destructive"} className="absolute right-5 top-5 capitalize">{card.rating}</Badge>}
                <p className="text-xl font-semibold leading-relaxed sm:text-2xl">{card.front}</p>
                <span className="absolute bottom-5 flex items-center gap-1.5 text-xs text-muted-foreground"><RotateCw className="h-3.5 w-3.5" />Tap to flip</span>
              </Card>
              <Card className="absolute inset-0 flex flex-col items-center justify-center overflow-auto border-primary/40 bg-gradient-to-br from-indigo-500/10 via-card to-violet-500/10 p-8 text-center [backface-visibility:hidden] [transform:rotateY(180deg)]">
                <div className="absolute left-5 top-5 text-xs font-semibold uppercase tracking-wider text-violet-400">Answer</div>
                <p className="text-lg leading-relaxed sm:text-xl">{card.back}</p>
              </Card>
            </button>
          </div>
          <div className="flex items-center justify-between gap-2">
            <Button variant="outline" size="icon" onClick={prev} aria-label="Previous card"><ChevronLeft /></Button>
            <div className={cn("flex flex-1 justify-center gap-2 transition-opacity", !flipped && "pointer-events-none opacity-40")} aria-hidden={!flipped}>
              <Button className="flex-1 border-success/40 text-success hover:bg-success/10 sm:flex-none sm:px-6" variant="outline" onClick={() => rate("easy")}>Easy</Button>
              <Button className="flex-1 border-warning/40 text-warning hover:bg-warning/10 sm:flex-none sm:px-6" variant="outline" onClick={() => rate("medium")}>Medium</Button>
              <Button className="flex-1 border-destructive/40 text-destructive hover:bg-destructive/10 sm:flex-none sm:px-6" variant="outline" onClick={() => rate("hard")}>Difficult</Button>
            </div>
            <Button variant="outline" size="icon" onClick={next} aria-label="Next card"><ChevronRight /></Button>
          </div>
          <p className="text-center text-xs text-muted-foreground">Flip to rate. Keyboard: ← → to move, Enter or F to flip.</p>
        </>
      )}
    </div>
  );
}
