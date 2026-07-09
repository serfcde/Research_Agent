"use client";
// components/research/node-detail-panel.tsx
import { X, Clock, Zap, Globe, MessageSquare, FileOutput, GitBranch } from "lucide-react";
import { AgentStep } from "@/types/research";

export function NodeDetailPanel({ step, onClose }: { step: AgentStep | null; onClose: () => void }) {
  if (!step) return null;
  return (
    <div className="fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col border-l border-border bg-background shadow-2xl">
      <div className="flex items-center justify-between border-b border-border px-5 py-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-widest text-primary">Agent Step</p>
          <h2 className="mt-0.5 text-lg font-semibold">{step.agentName}</h2>
        </div>
        <button onClick={onClose} className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"><X className="h-4 w-4" /></button>
      </div>
      <div className="flex-1 overflow-y-auto space-y-4 p-5">
        {(step.traceId || step.spanId) && (
          <section>
            <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <GitBranch className="h-3.5 w-3.5" />Pipelock Trace
            </div>
            <div className="rounded-md border border-primary/20 bg-primary/5 p-3 space-y-1.5 font-mono text-xs">
              {step.traceId && <div className="flex justify-between"><span className="text-muted-foreground">trace_id</span><span className="text-primary">{step.traceId}</span></div>}
              {step.spanId && <div className="flex justify-between"><span className="text-muted-foreground">span_id</span><span className="text-foreground">{step.spanId}</span></div>}
              {step.parentSpanId && <div className="flex justify-between"><span className="text-muted-foreground">parent_span_id</span><span className="text-muted-foreground">{step.parentSpanId}</span></div>}
              {step.pipelockRequestIds && step.pipelockRequestIds.length > 0 && (
                <div className="flex justify-between"><span className="text-muted-foreground">pipelock_req_ids</span><span className="text-accent">{step.pipelockRequestIds.join(", ")}</span></div>
              )}
            </div>
          </section>
        )}
        <section>
          <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground"><MessageSquare className="h-3.5 w-3.5" />Prompt</div>
          <div className="rounded-md border border-border bg-muted/40 p-3"><pre className="whitespace-pre-wrap font-mono text-xs leading-relaxed">{step.prompt || "—"}</pre></div>
        </section>
        <section>
          <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground"><FileOutput className="h-3.5 w-3.5" />Output</div>
          <div className="rounded-md border border-border bg-muted/40 p-3"><pre className="whitespace-pre-wrap font-mono text-xs leading-relaxed">{step.output || "—"}</pre></div>
        </section>
        <section>
          <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground"><Clock className="h-3.5 w-3.5" />Metrics</div>
          <div className="grid grid-cols-2 gap-2">
            <div className="rounded-md border border-border bg-muted/20 p-3"><p className="text-xs text-muted-foreground">Duration</p><p className="mt-1 text-base font-semibold">{step.durationMs ? (step.durationMs > 1000 ? `${(step.durationMs/1000).toFixed(1)}s` : `${step.durationMs}ms`) : "—"}</p></div>
            <div className="rounded-md border border-border bg-muted/20 p-3"><p className="text-xs text-muted-foreground">Est. Tokens</p><p className="mt-1 text-base font-semibold">{step.tokens ? step.tokens.toLocaleString() : "—"}</p></div>
          </div>
        </section>
      </div>
      <div className="border-t border-border px-5 py-3">
        <div className="flex items-center gap-2 text-xs text-muted-foreground"><Zap className="h-3 w-3 text-primary" />All API calls monitored by Pipelock v2.4.0</div>
      </div>
    </div>
  );
}