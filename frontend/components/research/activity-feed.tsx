import { ExternalLink } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { ToolExecution } from "@/types/research";

export function ToolActivityFeed({ tools }: { tools: ToolExecution[] }) {
  return (
    <div className="space-y-3">
      {tools.length === 0 ? (
        <p className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">Web search and tool activity will appear here as the Worker Agent executes tasks.</p>
      ) : (
        tools.map((tool) => (
          <div key={tool.id} className="rounded-lg border border-border bg-background/40 p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-medium">{tool.name}</p>
                <p className="mt-1 text-xs text-muted-foreground">{tool.query}</p>
              </div>
              <Badge status={tool.status}>{tool.status}</Badge>
            </div>
            <div className="mt-3 flex items-center gap-4 text-xs text-muted-foreground">
              <span>{tool.durationMs}ms</span>
              <span>{tool.sources} sources</span>
              <span className="inline-flex items-center gap-1 text-primary"><ExternalLink className="h-3 w-3" /> citations queued</span>
            </div>
          </div>
        ))
      )}
    </div>
  );
}
