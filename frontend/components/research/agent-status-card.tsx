import { CheckCircle2, CircleDashed, Loader2, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import type { AgentNode } from "@/types/research";
import { formatNumber } from "@/lib/utils";

const icons = {
  idle: CircleDashed,
  queued: CircleDashed,
  running: Loader2,
  completed: CheckCircle2,
  failed: XCircle
};

export function AgentStatusCard({ agent }: { agent: AgentNode }) {
  const Icon = icons[agent.status];
  return (
    <Card className="transition-transform hover:-translate-y-0.5">
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-sm font-semibold">{agent.name}</p>
            <p className="mt-1 text-xs text-muted-foreground">{agent.role}</p>
          </div>
          <Icon className={`h-5 w-5 ${agent.status === "running" ? "animate-spin text-primary" : "text-muted-foreground"}`} />
        </div>
        <div className="mt-4 flex items-center justify-between">
          <Badge status={agent.status}>{agent.status}</Badge>
          <span className="text-xs text-muted-foreground">{agent.progress}%</span>
        </div>
        <Progress className="mt-3" value={agent.progress} />
        <div className="mt-3 flex justify-between text-xs text-muted-foreground">
          <span>{agent.latencyMs ? `${agent.latencyMs}ms` : "ready"}</span>
          <span>{agent.tokens ? `${formatNumber(agent.tokens)} tok` : "0 tok"}</span>
        </div>
      </CardContent>
    </Card>
  );
}
