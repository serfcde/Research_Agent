// lib/server/trace.ts
// Lightweight distributed tracing — generates trace/span IDs
// and links each span to Pipelock's request_id

import "server-only";

export interface Span {
  trace_id: string;
  span_id: string;
  parent_span_id: string | null;
  name: string;
  start_time: string;
  end_time?: string;
  duration_ms?: number;
  pipelock_request_ids: string[];   // links to Pipelock's req-N IDs
  attributes: Record<string, string | number>;
}

export interface TraceContext {
  trace_id: string;
  spans: Span[];
}

// Generate a short hex ID
function shortId(prefix: string): string {
  return `${prefix}_${Math.random().toString(16).slice(2, 10)}`;
}

export function createTrace(): TraceContext {
  return {
    trace_id: shortId("trace"),
    spans: [],
  };
}

export function startSpan(
  ctx: TraceContext,
  name: string,
  parentSpanId: string | null,
  attributes: Record<string, string | number> = {}
): Span {
  const span: Span = {
    trace_id: ctx.trace_id,
    span_id: shortId(name.toLowerCase().replace(/\s+/g, "_")),
    parent_span_id: parentSpanId,
    name,
    start_time: new Date().toISOString(),
    pipelock_request_ids: [],
    attributes,
  };
  ctx.spans.push(span);
  return span;
}

export function endSpan(span: Span, attributes: Record<string, string | number> = {}): Span {
  span.end_time = new Date().toISOString();
  span.duration_ms = new Date(span.end_time).getTime() - new Date(span.start_time).getTime();
  span.attributes = { ...span.attributes, ...attributes };
  return span;
}

export function attachPipelockRequestId(span: Span, requestId: string): void {
  if (!span.pipelock_request_ids.includes(requestId)) {
    span.pipelock_request_ids.push(requestId);
  }
}

// Reconstruct graph nodes + edges from span hierarchy
export function spansToGraph(spans: Span[]): {
  nodes: GraphNode[];
  edges: GraphEdge[];
} {
  const nodes: GraphNode[] = spans.map((span) => ({
    id: span.span_id,
    label: span.name,
    traceId: span.trace_id,
    spanId: span.span_id,
    parentSpanId: span.parent_span_id,
    durationMs: span.duration_ms,
    pipelockRequestIds: span.pipelock_request_ids,
    attributes: span.attributes,
  }));

  // Edges derived entirely from parent_span_id relationships — NOT hardcoded
  const edges: GraphEdge[] = spans
    .filter((span) => span.parent_span_id !== null)
    .map((span) => ({
      from: span.parent_span_id!,
      to: span.span_id,
      label: span.attributes.transition_label as string | undefined,
    }));

  return { nodes, edges };
}

export interface GraphNode {
  id: string;
  label: string;
  traceId: string;
  spanId: string;
  parentSpanId: string | null;
  durationMs?: number;
  pipelockRequestIds: string[];
  attributes: Record<string, string | number>;
}

export interface GraphEdge {
  from: string;
  to: string;
  label?: string;
}