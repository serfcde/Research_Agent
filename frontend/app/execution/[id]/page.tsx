"use client";

import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { Clock3, Cpu, FileText, Loader2, TimerReset } from "lucide-react";
import { AgentStatusCard } from "@/components/research/agent-status-card";
import { ToolActivityFeed } from "@/components/research/activity-feed";
import { LiveLogs } from "@/components/research/live-logs";
import { WorkflowGraph } from "@/components/research/workflow-graph";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { useResearchStream } from "@/hooks/use-research-stream";
import { researchApi } from "@/services/api";
import { useResearchStore } from "@/store/research-store";
import { formatNumber } from "@/lib/utils";

export default function LiveExecutionPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const activeRun = useResearchStore((state) => state.activeRun);
  const setActiveRun = useResearchStore((state) => state.setActiveRun);
  const pushToast = useResearchStore((state) => state.pushToast);

  useResearchStream(params.id === "demo" ? activeRun?.id : params.id);

  useEffect(() => {
    const id = params.id === "demo" ? "ars-20260511-qc-edge" : params.id;
    researchApi.status(id).then(setActiveRun).catch(() => pushToast({ title: "Could not load workflow", description: "Showing local state where available.", tone: "error" }));
  }, [params.id, pushToast, setActiveRun]);

  if (!activeRun) {
    return <div className="grid gap-4 lg:grid-cols-4">{Array.from({ length: 8 }).map((_, index) => <Skeleton key={index} className="h-40" />)}</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
        <div>
          <p className="text-sm text-primary">Live Research Execution</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-normal">{activeRun.prompt}</h1>
          <p className="mt-2 text-sm text-muted-foreground">Current task: {activeRun.currentTask}</p>
        </div>
        <Button onClick={() => router.push(`/reports/${activeRun.id}`)} disabled={!activeRun.report}>
          <FileText className="h-4 w-4" />
          Open Report
        </Button>
      </div>

      <Card>
        <CardContent className="p-5">
          <div className="mb-3 flex justify-between text-sm">
            <span>Overall progress</span>
            <span className="text-muted-foreground">{activeRun.progress}%</span>
          </div>
          <Progress value={activeRun.progress} className="h-3" />
        </CardContent>
      </Card>

      <WorkflowGraph agents={activeRun.agents} />

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        {(activeRun.agents || []).map((agent) => (
  <AgentStatusCard key={agent.id} agent={agent} />
))}
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.35fr_0.65fr]">
        <Card>
          <CardHeader>
            <CardTitle>Live Logs Terminal</CardTitle>
            <CardDescription>Streaming events from agent orchestration and tools.</CardDescription>
          </CardHeader>
          <CardContent>
            <LiveLogs logs={activeRun.logs ?? []} />
          </CardContent>
        </Card>

        <div className="space-y-4">
          <InfoCard icon={Cpu} title="Token Usage" value={formatNumber(activeRun.tokenUsage?.total ?? 0)} detail={`${formatNumber(activeRun.tokenUsage?.prompt ?? 0)} prompt · ${formatNumber(activeRun.tokenUsage?.completion ?? 0)} completion`} />
          <InfoCard icon={TimerReset} title="Estimated Completion" value={activeRun.estimatedCompletion ?? "—"} detail={activeRun.status === "completed" ? "Workflow finished" : "Adaptive estimate"} />
          <Card>
            <CardHeader>
              <CardTitle>Tool Execution</CardTitle>
              <CardDescription>Search jobs, source collection, and retrieval status.</CardDescription>
            </CardHeader>
            <CardContent>
              <ToolActivityFeed tools={activeRun.tools ?? []} />
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function InfoCard({ icon: Icon, title, value, detail }: { icon: typeof Clock3; title: string; value: string; detail: string }) {
  return (
    <Card>
      <CardContent className="flex items-center gap-4 p-5">
        <div className="flex h-11 w-11 items-center justify-center rounded-md bg-primary/15 text-primary">
          <Icon className="h-5 w-5" />
        </div>
        <div>
          <p className="text-sm text-muted-foreground">{title}</p>
          <p className="text-xl font-semibold">{value}</p>
          <p className="text-xs text-muted-foreground">{detail}</p>
        </div>
      </CardContent>
    </Card>
  );
}
