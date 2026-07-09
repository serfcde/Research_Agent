"use client";

// app/execution/[id]/graph/page.tsx
// Visual execution trace graph — nodes from trace spans, edges from parent_span_id

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { useResearchStore } from "@/store/research-store";
import { NodeDetailPanel } from "@/components/research/node-detail-panel";
import { Button } from "@/components/ui/button";
import type { AgentStep } from "@/types/research";

// ── Layout constants ────────────────────────────────────────────────────────
const NODE_W = 190;
const NODE_H = 68;
const H_GAP = 56;
const V_GAP = 96;

// ── Helpers ──────────────────────────────────────────────────────────────────
function cleanLabel(raw: string): string {
  return raw
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase())
    .replace("Research Run", "Start")
    .replace(/Web Search (\d+)/, "Web Search — Task $1")
    .replace("Prompt Enhancer", "Prompt Enhancer")
    .replace("Planner Agent", "Planner Agent")
    .replace("Worker Agent", "Worker Agent")
    .replace("Formatter Agent", "Formatter Agent");
}

function statusStyle(status: string) {
  switch (status) {
    case "completed": return { border: "#22c55e", bg: "rgba(34,197,94,0.08)", dot: "#22c55e" };
    case "running":   return { border: "#eab308", bg: "rgba(234,179,8,0.08)", dot: "#eab308" };
    case "failed":    return { border: "#ef4444", bg: "rgba(239,68,68,0.08)", dot: "#ef4444" };
    default:          return { border: "#4b5563", bg: "rgba(75,85,99,0.08)", dot: "#4b5563" };
  }
}

// ── Tree layout ───────────────────────────────────────────────────────────────
function layoutTree(nodes: any[], edges: any[]): Record<string, { x: number; y: number }> {
  if (!nodes.length) return {};

  const children: Record<string, string[]> = {};
  const parentOf: Record<string, string> = {};
  nodes.forEach((n) => { children[n.id] = []; });
  edges.forEach((e) => {
    if (children[e.from] !== undefined) children[e.from].push(e.to);
    parentOf[e.to] = e.from;
  });

  const root = nodes.find((n) => !parentOf[n.id]);
  if (!root) return {};

  const subtreeW: Record<string, number> = {};
  function calcW(id: string): number {
    const kids = children[id] || [];
    if (!kids.length) { subtreeW[id] = NODE_W; return NODE_W; }
    const total = kids.reduce((s, k) => s + calcW(k) + H_GAP, -H_GAP);
    subtreeW[id] = Math.max(NODE_W, total);
    return subtreeW[id];
  }
  calcW(root.id);

  const pos: Record<string, { x: number; y: number }> = {};
  function assign(id: string, x: number, y: number) {
    pos[id] = { x, y };
    const kids = children[id] || [];
    if (!kids.length) return;
    const totalW = kids.reduce((s, k) => s + subtreeW[k] + H_GAP, -H_GAP);
    let cx = x - totalW / 2;
    kids.forEach((kid) => {
      assign(kid, cx + subtreeW[kid] / 2, y + NODE_H + V_GAP);
      cx += subtreeW[kid] + H_GAP;
    });
  }
  assign(root.id, 0, 0);
  return pos;
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function TraceGraphPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const activeRun = useResearchStore((s) => s.activeRun);
  const [selectedStep, setSelectedStep] = useState<AgentStep | null>(null);

  const graph = activeRun?.traceGraph;
  const steps = activeRun?.steps ?? [];

  if (!graph?.nodes?.length) {
    return (
      <div className="flex h-96 flex-col items-center justify-center gap-3">
        <p className="text-muted-foreground">No trace graph yet — run a research query first.</p>
        <Button variant="outline" onClick={() => router.back()}>Go back</Button>
      </div>
    );
  }

  const positions = layoutTree(graph.nodes, graph.edges);

  // SVG canvas bounds
  const allPos = Object.values(positions);
  const minX = Math.min(...allPos.map((p) => p.x)) - NODE_W / 2 - 60;
  const maxX = Math.max(...allPos.map((p) => p.x)) + NODE_W / 2 + 60;
  const minY = Math.min(...allPos.map((p) => p.y)) - 30;
  const maxY = Math.max(...allPos.map((p) => p.y)) + NODE_H + 60;
  const svgW = maxX - minX;
  const svgH = maxY - minY;
  const ox = -minX; // offset x
  const oy = -minY; // offset y

  const handleClick = (node: any) => {
    const step = steps.find((s) => s.spanId === node.id || s.agentId === node.id);
    if (step) setSelectedStep(step);
  };

  return (
    <div className="space-y-5 p-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <button
            onClick={() => router.back()}
            className="mb-2 flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="h-3 w-3" /> Back to execution
          </button>
          <h1 className="text-xl font-semibold">Execution Trace Graph</h1>
          {activeRun?.traceId && (
            <p className="mt-1 font-mono text-xs text-muted-foreground">
              trace_id: <span className="text-primary">{activeRun.traceId}</span>
              &nbsp;&nbsp;·&nbsp;&nbsp;
              {graph.nodes.length} spans &nbsp;·&nbsp; {graph.edges.length} transitions
            </p>
          )}
        </div>
        <div className="flex gap-3 text-xs text-muted-foreground">
          {[["#22c55e", "Completed"], ["#eab308", "Running"], ["#ef4444", "Failed"], ["#4b5563", "Queued"]].map(
            ([color, label]) => (
              <div key={label} className="flex items-center gap-1.5">
                <div style={{ width: 8, height: 8, borderRadius: 2, background: color }} />
                {label}
              </div>
            )
          )}
        </div>
      </div>

      {/* Graph canvas */}
      <div className="overflow-auto rounded-xl border border-border bg-muted/5 p-6">
        <div style={{ position: "relative", width: svgW, height: svgH, minWidth: 600 }}>

          {/* SVG layer — edges + arrowheads */}
          <svg
            style={{ position: "absolute", top: 0, left: 0, overflow: "visible", pointerEvents: "none" }}
            width={svgW}
            height={svgH}
          >
            <defs>
              <marker id="arrowhead" markerWidth="9" markerHeight="9" refX="7" refY="3.5" orient="auto">
                <polygon points="0 0, 9 3.5, 0 7" fill="#4b5563" />
              </marker>
            </defs>

            {graph.edges.map((edge: any, i: number) => {
              const from = positions[edge.from];
              const to = positions[edge.to];
              if (!from || !to) return null;

              const x1 = from.x + ox;
              const y1 = from.y + oy + NODE_H;
              const x2 = to.x + ox;
              const y2 = to.y + oy;
              const cp1y = y1 + V_GAP * 0.45;
              const cp2y = y2 - V_GAP * 0.45;

              return (
                <g key={i}>
                  <path
                    d={`M${x1},${y1} C${x1},${cp1y} ${x2},${cp2y} ${x2},${y2}`}
                    fill="none"
                    stroke="#374151"
                    strokeWidth={1.5}
                    markerEnd="url(#arrowhead)"
                  />
                  {edge.label && (
                    <text
                      x={(x1 + x2) / 2}
                      y={(y1 + y2) / 2}
                      textAnchor="middle"
                      fontSize={10}
                      fill="#6b7280"
                      dy={-5}
                    >
                      {edge.label}
                    </text>
                  )}
                </g>
              );
            })}
          </svg>

          {/* HTML node layer */}
          {graph.nodes.map((node: any) => {
            const pos = positions[node.id];
            if (!pos) return null;

            const step = steps.find((s) => s.spanId === node.id || s.agentId === node.id);
            const status = step
              ? step.durationMs && step.durationMs > 0
                ? "completed"
                : "running"
              : "queued";
            const style = statusStyle(status);
            const label = cleanLabel(node.label);
            const duration = step?.durationMs || node.durationMs;
            const isClickable = !!step;

            return (
              <div
                key={node.id}
                onClick={() => isClickable && handleClick(node)}
                style={{
                  position: "absolute",
                  left: pos.x + ox - NODE_W / 2,
                  top: pos.y + oy,
                  width: NODE_W,
                  height: NODE_H,
                  border: `1.5px solid ${style.border}`,
                  background: style.bg,
                  borderRadius: 10,
                  cursor: isClickable ? "pointer" : "default",
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "center",
                  padding: "6px 12px",
                  gap: 3,
                  transition: "transform 0.15s, box-shadow 0.15s",
                  userSelect: "none",
                }}
                className={isClickable ? "hover:scale-105 hover:shadow-lg hover:shadow-black/20" : ""}
              >
                {/* Status dot */}
                <div style={{ position: "absolute", top: 8, right: 8, width: 6, height: 6, borderRadius: "50%", background: style.dot }} />

                {/* Label */}
                <span style={{ fontSize: 12, fontWeight: 600, color: "var(--foreground)", textAlign: "center", lineHeight: 1.3 }}>
                  {label}
                </span>

                {/* Duration */}
                {duration ? (
                  <span style={{ fontSize: 10, color: style.dot, fontWeight: 500 }}>
                    {duration > 1000 ? `${(duration / 1000).toFixed(1)}s` : `${duration}ms`}
                  </span>
                ) : null}

                {/* Click hint */}
                {isClickable && (
                  <span style={{ fontSize: 9, color: "#6b7280", letterSpacing: "0.02em" }}>
                    click to inspect
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Trace span list — text fallback below graph */}
      <div className="space-y-1.5">
        <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Trace Spans ({graph.edges.length} transitions)
        </p>
        {graph.edges.map((edge: any, i: number) => {
          const fromNode = graph.nodes.find((n: any) => n.id === edge.from);
          const toNode = graph.nodes.find((n: any) => n.id === edge.to);
          const toStep = steps.find((s) => s.spanId === edge.to || s.agentId === edge.to);
          return (
            <div
              key={i}
              className="flex items-center gap-2 rounded-md border border-border bg-muted/10 px-4 py-2 text-sm font-mono"
            >
              <span className="text-primary">{cleanLabel(fromNode?.label || edge.from)}</span>
              <span className="text-muted-foreground">
                ──{edge.label ? ` ${edge.label} ` : "─"}──→
              </span>
              <span className="text-foreground">{cleanLabel(toNode?.label || edge.to)}</span>
              {toStep?.durationMs ? (
                <span className="ml-auto text-xs text-muted-foreground">
                  {toStep.durationMs > 1000
                    ? `${(toStep.durationMs / 1000).toFixed(1)}s`
                    : `${toStep.durationMs}ms`}
                </span>
              ) : null}
              {toStep?.spanId && (
                <span className="text-xs text-muted-foreground/60">[{toStep.spanId}]</span>
              )}
            </div>
          );
        })}
      </div>

      {/* Detail panel */}
      {selectedStep && (
        <>
          <div
            className="fixed inset-0 z-40 bg-background/60 backdrop-blur-sm"
            onClick={() => setSelectedStep(null)}
          />
          <NodeDetailPanel step={selectedStep} onClose={() => setSelectedStep(null)} />
        </>
      )}
    </div>
  );
}