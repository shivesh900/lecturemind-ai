import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { ReactFlow, Background, Controls, MiniMap, MarkerType, Handle, Position, type Edge, type Node, type NodeProps } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { forceCenter, forceCollide, forceLink, forceManyBody, forceSimulation, forceX, forceY, type SimulationNodeDatum } from "d3-force";
import { List, Network, RefreshCw, Search, X, PlayCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ErrorNote, ModeBadge } from "@/components/common";
import { useApi } from "@/hooks/useApi";
import { useTheme } from "@/hooks/useTheme";
import { ApiError, post } from "@/services/api";
import { cn } from "@/utils/cn";
import type { KnowledgeMap, KnowledgeNode } from "@/types";
import { useWorkspace } from "./context";
import { NotReady, TabSkeleton, TimeChip } from "./shared";

const TYPE_STYLE: Record<string, { color: string; label: string }> = {
  topic: { color: "#6366f1", label: "Topic" },
  subtopic: { color: "#8b5cf6", label: "Subtopic" },
  concept: { color: "#0ea5e9", label: "Concept" },
  definition: { color: "#10b981", label: "Definition" },
  entity: { color: "#f59e0b", label: "Person / entity" },
  date: { color: "#f97316", label: "Date / event" },
  formula: { color: "#ec4899", label: "Formula" },
  keyword: { color: "#64748b", label: "Keyword" },
};

type GNode = Node<{ node: KnowledgeNode; selected: boolean; dim: boolean }>;

function ConceptNode({ data }: NodeProps<GNode>) {
  const { node, selected, dim } = data;
  const st = TYPE_STYLE[node.type] || TYPE_STYLE.concept;
  const big = node.type === "topic";
  return (
    <div className={cn("rounded-xl border-2 bg-card px-3 py-2 text-center shadow-lg transition-all", big ? "min-w-[150px] text-sm font-bold" : "max-w-[180px] text-xs font-medium", selected && "ring-4 ring-primary/40", dim && "opacity-25")}
      style={{ borderColor: st.color, boxShadow: selected ? `0 0 24px ${st.color}66` : undefined }}>
      <Handle type="target" position={Position.Top} className="!h-1 !w-1 !border-0 !bg-transparent" />
      <div className="mb-0.5 text-[9px] font-semibold uppercase tracking-wider" style={{ color: st.color }}>{st.label}</div>
      <div className="leading-snug text-foreground">{node.label}</div>
      <Handle type="source" position={Position.Bottom} className="!h-1 !w-1 !border-0 !bg-transparent" />
    </div>
  );
}
const nodeTypes = { concept: ConceptNode };

interface SimNode extends SimulationNodeDatum { id: string; type: string }

function layout(map: KnowledgeMap): Record<string, { x: number; y: number }> {
  const nodes: SimNode[] = map.nodes.map((n, i) => ({ id: n.id, type: n.type, x: Math.cos(i) * 200, y: Math.sin(i) * 200 }));
  const links = map.edges.map((e) => ({ source: e.source, target: e.target }));
  const sim = forceSimulation(nodes)
    .force("link", forceLink(links).id((d: any) => d.id).distance((l: any) => (l.source.type === "topic" || l.target.type === "topic" ? 150 : 115)).strength(0.7))
    .force("charge", forceManyBody().strength(-520))
    .force("center", forceCenter(0, 0))
    .force("collide", forceCollide(82))
    .force("x", forceX(0).strength(0.07))
    .force("y", forceY(0).strength(0.1))
    .stop();
  for (let i = 0; i < 400; i++) sim.tick();
  return Object.fromEntries(nodes.map((n) => [n.id, { x: n.x || 0, y: n.y || 0 }]));
}

export default function KnowledgeTab() {
  const { lecture, reload: reloadLecture, jumpTo } = useWorkspace();
  const { resolved } = useTheme();
  const has = lecture.available?.knowledge_map;
  const { data, error, loading, reload } = useApi<KnowledgeMap>(has ? `/api/lectures/${lecture.id}/knowledge-map` : null, [has, lecture.status]);
  const [selected, setSelected] = useState<string | null>(null);
  const [view, setView] = useState<"graph" | "list">(() => (window.innerWidth < 640 ? "list" : "graph"));
  const [q, setQ] = useState("");
  const [typeFilter, setTypeFilter] = useState<string | null>(null);
  const [regen, setRegen] = useState(false);

  const positions = useMemo(() => (data ? layout(data) : {}), [data]);
  const neighbours = useMemo(() => {
    if (!data || !selected) return null;
    const s = new Set([selected]);
    data.edges.forEach((e) => { if (e.source === selected) s.add(e.target); if (e.target === selected) s.add(e.source); });
    return s;
  }, [data, selected]);

  const rfNodes: GNode[] = useMemo(() => (data ? data.nodes.map((n) => ({
    id: n.id, type: "concept", position: positions[n.id] || { x: 0, y: 0 },
    data: { node: n, selected: n.id === selected, dim: !!neighbours && !neighbours.has(n.id) },
  })) : []), [data, positions, selected, neighbours]);
  const rfEdges: Edge[] = useMemo(() => (data ? data.edges.map((e, i) => {
    const active = !neighbours || (neighbours.has(e.source) && neighbours.has(e.target) && (e.source === selected || e.target === selected));
    return {
      id: `e${i}`, source: e.source, target: e.target, label: active && neighbours ? e.relation : undefined,
      animated: !!neighbours && active, style: { stroke: active ? "#818cf8" : "#64748b", strokeWidth: active && neighbours ? 2 : 1.2, opacity: active ? 0.9 : 0.15 },
      labelStyle: { fontSize: 10, fill: resolved === "dark" ? "#c7d2fe" : "#3730a3" }, labelBgStyle: { fill: resolved === "dark" ? "#0b1020" : "#ffffff" },
      markerEnd: { type: MarkerType.ArrowClosed, color: "#818cf8", width: 14, height: 14 },
    };
  }) : []), [data, neighbours, selected, resolved]);

  useEffect(() => setSelected(null), [data]);

  if (!has || (lecture.status === "processing" && lecture.steps.knowledge_map?.status !== "completed"))
    return <NotReady lecture={lecture} what="knowledge map" icon={<Network />} />;
  if (error) return <ErrorNote message={error.message} onRetry={() => reload()} />;
  if (loading || !data) return <TabSkeleton />;

  const sel = data.nodes.find((n) => n.id === selected);
  const related = sel ? data.edges.filter((e) => e.source === sel.id || e.target === sel.id).map((e) => ({ rel: e.relation, other: data.nodes.find((n) => n.id === (e.source === sel.id ? e.target : e.source)), out: e.source === sel.id })) : [];
  const listNodes = data.nodes.filter((n) => (!typeFilter || n.type === typeFilter) && (!q || (n.label + " " + n.description).toLowerCase().includes(q.toLowerCase())));
  const presentTypes = Array.from(new Set(data.nodes.map((n) => n.type)));

  const regenerate = async () => {
    setRegen(true);
    try { await post(`/api/lectures/${lecture.id}/knowledge-map`); toast.success("Rebuilding the knowledge map…"); await reloadLecture(true); }
    catch (e) { toast.error((e as ApiError).message); } finally { setRegen(false); }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Tabs value={view} onValueChange={(v) => setView(v as "graph" | "list")}>
          <TabsList><TabsTrigger value="graph"><Network />Graph</TabsTrigger><TabsTrigger value="list"><List />Concept list</TabsTrigger></TabsList>
        </Tabs>
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">{data.nodes.length} nodes · {data.edges.length} links</span>
          <ModeBadge mode={data.mode} />
          <Button size="sm" variant="ghost" onClick={regenerate} loading={regen} disabled={lecture.status !== "completed"}><RefreshCw />Rebuild</Button>
        </div>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {presentTypes.map((t) => (
          <button key={t} onClick={() => setTypeFilter(typeFilter === t ? null : t)} className={cn("inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs transition-colors", typeFilter === t ? "border-primary bg-primary/10" : "hover:bg-secondary")}>
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: TYPE_STYLE[t]?.color }} />{TYPE_STYLE[t]?.label || t}
            <span className="text-muted-foreground">{data.nodes.filter((n) => n.type === t).length}</span>
          </button>
        ))}
      </div>

      {view === "graph" ? (
        <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
          <Card className="h-[520px] overflow-hidden sm:h-[600px]">
            <ReactFlow nodes={rfNodes} edges={rfEdges} nodeTypes={nodeTypes} fitView fitViewOptions={{ padding: 0.08 }} style={{ background: "transparent" }} minZoom={0.2} maxZoom={2}
              onNodeClick={(_, n) => setSelected(n.id === selected ? null : n.id)} onPaneClick={() => setSelected(null)} colorMode={resolved} proOptions={{ hideAttribution: true }}>
              <Background gap={24} size={1} color={resolved === "dark" ? "#1e2547" : "#dfe3f3"} />
              <Controls showInteractive={false} />
              <MiniMap pannable zoomable nodeColor={(n) => TYPE_STYLE[(n.data as any)?.node?.type]?.color || "#6366f1"} bgColor={resolved === "dark" ? "#0d1226" : "#ffffff"} maskColor={resolved === "dark" ? "rgba(7,11,26,.6)" : "rgba(240,242,250,.6)"} className="!hidden !rounded-lg !border md:!block" style={{ width: 150, height: 100 }} />
            </ReactFlow>
          </Card>
          <Card className="h-fit">
            {sel ? (
              <>
                <CardHeader className="pb-2">
                  <div className="flex items-start justify-between gap-2">
                    <Badge style={{ background: (TYPE_STYLE[sel.type]?.color || "#6366f1") + "26", color: TYPE_STYLE[sel.type]?.color }}>{TYPE_STYLE[sel.type]?.label}</Badge>
                    <button onClick={() => setSelected(null)} className="text-muted-foreground hover:text-foreground" aria-label="Close details"><X className="h-4 w-4" /></button>
                  </div>
                  <CardTitle className="pt-1 text-lg">{sel.label}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4 text-sm">
                  <p className="leading-6 text-foreground/90">{sel.description || "No description extracted."}</p>
                  {sel.timestamp != null && (
                    <Button size="sm" variant="outline" className="w-full" onClick={() => jumpTo(sel.timestamp!)}><PlayCircle />Hear it at <TimeChip t={sel.timestamp} /></Button>
                  )}
                  {related.length > 0 && (
                    <div>
                      <div className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Connections</div>
                      <ul className="space-y-1">
                        {related.map((r, i) => r.other && (
                          <li key={i}><button onClick={() => setSelected(r.other!.id)} className="w-full rounded-lg px-2 py-1.5 text-left text-xs hover:bg-secondary">
                            <span className="text-muted-foreground">{r.out ? r.rel : `← ${r.rel}`}</span> <span className="font-medium">{r.other.label}</span>
                          </button></li>
                        ))}
                      </ul>
                    </div>
                  )}
                </CardContent>
              </>
            ) : (
              <CardContent className="p-6 text-center text-sm text-muted-foreground">
                <Network className="mx-auto mb-3 h-8 w-8 text-primary/60" />
                Click a node to see its explanation, its connections and the moment it was discussed. Drag to pan, scroll to zoom.
                {data.keywords.length > 0 && (
                  <div className="mt-5 text-left">
                    <div className="mb-2 text-xs font-semibold uppercase tracking-wider">Important keywords</div>
                    <div className="flex flex-wrap gap-1.5">{data.keywords.slice(0, 18).map((k) => <Badge key={k} variant="secondary">{k}</Badge>)}</div>
                  </div>
                )}
              </CardContent>
            )}
          </Card>
        </div>
      ) : (
        <Card>
          <div className="border-b p-3">
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search concepts…" className="pl-9" aria-label="Search concepts" />
            </div>
          </div>
          <ul className="divide-y" aria-label="Concepts">
            {listNodes.map((n) => (
              <li key={n.id} className="flex gap-3 p-4">
                <span className="mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: TYPE_STYLE[n.type]?.color }} aria-hidden />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">{n.label}</span>
                    <span className="text-xs text-muted-foreground">{TYPE_STYLE[n.type]?.label}</span>
                    {n.timestamp != null && <TimeChip t={n.timestamp} onClick={jumpTo} />}
                  </div>
                  {n.description && <p className="mt-1 text-sm leading-6 text-muted-foreground">{n.description}</p>}
                  {(() => {
                    const rel = data.edges.filter((e) => e.source === n.id).map((e) => `${e.relation} ${data.nodes.find((x) => x.id === e.target)?.label}`);
                    return rel.length ? <p className="mt-1 text-xs text-muted-foreground/80">→ {rel.slice(0, 4).join(" · ")}</p> : null;
                  })()}
                </div>
              </li>
            ))}
            {listNodes.length === 0 && <li className="p-8 text-center text-sm text-muted-foreground">No concepts match.</li>}
          </ul>
        </Card>
      )}
    </div>
  );
}
