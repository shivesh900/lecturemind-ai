import { useEffect, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { BookOpen, FileText, Network, Search as SearchIcon, Sparkles, AudioLines, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { EmptyState, ErrorNote, PageHeader } from "@/components/common";
import { ApiError, get } from "@/services/api";
import { formatTs } from "@/utils/format";
import type { SearchGroup } from "@/types";

const KIND: Record<string, { label: string; icon: any; tab: string }> = {
  transcript: { label: "Transcript", icon: AudioLines, tab: "transcript" },
  semantic: { label: "Semantic match", icon: Sparkles, tab: "transcript" },
  notes: { label: "Notes", icon: FileText, tab: "notes" },
  concept: { label: "Concept", icon: Network, tab: "knowledge" },
  lecture: { label: "Lecture", icon: BookOpen, tab: "" },
};

export default function SearchPage() {
  const [params, setParams] = useSearchParams();
  const initial = params.get("q") || "";
  const [q, setQ] = useState(initial);
  const [mode, setMode] = useState(params.get("mode") || "hybrid");
  const [data, setData] = useState<{ results: SearchGroup[]; total: number; semantic_available: boolean; semantic_used: boolean } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const query = params.get("q");
    if (!query || query.length < 2) return;
    setQ(query);
    setLoading(true);
    setError("");
    get<any>(`/api/search?q=${encodeURIComponent(query)}&mode=${mode}`)
      .then(setData).catch((e: ApiError) => setError(e.message)).finally(() => setLoading(false));
  }, [params, mode]);

  const submit = (e: FormEvent) => { e.preventDefault(); if (q.trim().length >= 2) setParams({ q: q.trim(), mode }); };

  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader icon={<SearchIcon />} title="Search everything" description="Search across all your lectures' transcripts, notes and extracted concepts. Only your own content is searched." />
      <form onSubmit={submit} className="flex flex-col gap-3 sm:flex-row">
        <div className="relative flex-1">
          <SearchIcon className="pointer-events-none absolute left-3.5 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="e.g. how is word error rate computed?" className="h-12 rounded-xl pl-11 text-base" autoFocus aria-label="Search query" />
        </div>
        <Button type="submit" size="lg" variant="gradient" disabled={q.trim().length < 2}>Search</Button>
      </form>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <Tabs value={mode} onValueChange={(m) => { setMode(m); if (params.get("q")) setParams({ q: params.get("q")!, mode: m }); }}>
          <TabsList>
            <TabsTrigger value="hybrid">Hybrid</TabsTrigger>
            <TabsTrigger value="keyword">Keyword</TabsTrigger>
            <TabsTrigger value="semantic" disabled={data ? !data.semantic_available : false}>Semantic</TabsTrigger>
          </TabsList>
        </Tabs>
        {data && !data.semantic_available && <span className="text-xs text-muted-foreground">Semantic search needs an OpenAI key (embeddings). Keyword search is active.</span>}
      </div>

      <div className="mt-6 space-y-4">
        {error && <ErrorNote message={error} />}
        {loading && Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-36 rounded-2xl" />)}
        {!loading && !params.get("q") && (
          <EmptyState icon={<SearchIcon />} title="Search your knowledge base" description="Try a concept, a definition, a formula or a question. Semantic search finds matching meaning even when the words differ." />
        )}
        {!loading && data && params.get("q") && data.results.length === 0 && (
          <EmptyState icon={<SearchIcon />} title="No matches" description={`Nothing in your lectures matches “${params.get("q")}”.`} />
        )}
        {!loading && data && data.results.length > 0 && <p className="text-sm text-muted-foreground">{data.total} matches in {data.results.length} lecture{data.results.length > 1 ? "s" : ""}</p>}
        {!loading && data?.results.map((g) => (
          <Card key={g.lecture_id} className="animate-fade-up">
            <CardHeader className="flex-row items-center justify-between space-y-0 pb-2">
              <div className="min-w-0">
                <CardTitle className="truncate"><Link to={`/app/lectures/${g.lecture_id}`} className="hover:text-primary">{g.title}</Link></CardTitle>
                {g.subject && <p className="text-xs text-muted-foreground">{g.subject}</p>}
              </div>
              <Button asChild size="sm" variant="ghost"><Link to={`/app/lectures/${g.lecture_id}`}>Open <ArrowRight /></Link></Button>
            </CardHeader>
            <CardContent className="space-y-1.5">
              {g.matches.map((m, i) => {
                const k = KIND[m.kind] || KIND.transcript;
                const to = `/app/lectures/${g.lecture_id}${k.tab ? "/" + k.tab : ""}${m.timestamp != null && k.tab === "transcript" ? `?t=${Math.floor(m.timestamp)}` : ""}`;
                return (
                  <Link key={i} to={to} className="flex items-start gap-3 rounded-xl p-2.5 transition-colors hover:bg-secondary/60">
                    <span className="mt-0.5 rounded-md bg-primary/10 p-1.5 text-primary"><k.icon className="h-3.5 w-3.5" /></span>
                    <div className="min-w-0 flex-1">
                      <div className="mb-0.5 flex flex-wrap items-center gap-2 text-xs">
                        <span className="font-medium text-muted-foreground">{k.label}</span>
                        {m.timestamp != null && <Badge variant="default" className="font-mono">{formatTs(m.timestamp)}</Badge>}
                        {m.similarity != null && <span className="text-muted-foreground">similarity {m.similarity.toFixed(2)}</span>}
                      </div>
                      <p className="line-clamp-2 text-sm">{m.text}</p>
                    </div>
                  </Link>
                );
              })}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
