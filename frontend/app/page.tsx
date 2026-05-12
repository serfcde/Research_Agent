"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { ArrowRight, BrainCircuit, Loader2, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label, Select, SelectContent, SelectItem, SelectTrigger, SelectValue, Textarea } from "@/components/ui/form";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { examplePrompts } from "@/lib/mock-data";
import { researchApi } from "@/services/api";
import { useResearchStore } from "@/store/research-store";
import type { ResearchDepth } from "@/types/research";

export default function DashboardPage() {
  const router = useRouter();
  const [prompt, setPrompt] = useState("Research Quantum Computing and Edge AI");
  const [depth, setDepth] = useState<ResearchDepth>("medium");
  const [loading, setLoading] = useState(false);
  const runs = useResearchStore((state) => state.runs);
  const setRuns = useResearchStore((state) => state.setRuns);
  const setActiveRun = useResearchStore((state) => state.setActiveRun);
  const pushToast = useResearchStore((state) => state.pushToast);

  useEffect(() => {
    researchApi.history().then(setRuns).catch(() => undefined);
  }, [setRuns]);

  async function startResearch() {
    if (prompt.trim().length < 8) {
      pushToast({ title: "Prompt is too short", description: "Add two clear research topics before starting.", tone: "error" });
      return;
    }
    setLoading(true);
    try {
      const run = await researchApi.start({ prompt, depth });
      setActiveRun(run);
      pushToast({ title: "Research started", description: "Agents are initializing the workflow.", tone: "success" });
      router.push(`/execution/${run.id}`);
    } catch {
      pushToast({ title: "Unable to start research", description: "Check the API service and try again.", tone: "error" });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <section>
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
          <Card className="overflow-hidden">
            <CardHeader className="pb-3">
              <div className="flex items-center gap-2 text-sm text-primary"><Sparkles className="h-4 w-4" /> Multi-agent research workspace</div>
              <CardTitle className="text-2xl sm:text-3xl">Agentic Research System</CardTitle>
              <CardDescription>Launch a structured research workflow across Prompt Enhancer, Planner, Worker, Web Search, and Formatter agents.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
              <div className="space-y-2">
                <Label htmlFor="prompt">Research prompt</Label>
                <Textarea id="prompt" value={prompt} onChange={(event) => setPrompt(event.target.value)} className="min-h-40 text-base" placeholder="Research Quantum Computing and Edge AI" />
              </div>
              <div className="grid gap-3 sm:grid-cols-[220px_1fr]">
                <div className="space-y-2">
                  <Label>Research depth</Label>
                  <Select value={depth} onValueChange={(value) => setDepth(value as ResearchDepth)}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="quick">Quick scan</SelectItem>
                      <SelectItem value="medium">Medium research</SelectItem>
                      <SelectItem value="deep">Deep analysis</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex items-end">
                  <Button size="lg" className="w-full sm:w-auto" onClick={startResearch} disabled={loading}>
                    {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <BrainCircuit className="h-4 w-4" />}
                    Start Research
                    <ArrowRight className="h-4 w-4" />
                  </Button>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                {examplePrompts.map((item) => (
                  <button key={item} onClick={() => setPrompt(item)} className="rounded-full border border-border bg-background/50 px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground">
                    {item}
                  </button>
                ))}
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </section>

      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Recent Research</h2>
          <Button variant="ghost" size="sm" onClick={() => router.push("/history")}>View all</Button>
        </div>
        {runs.length === 0 ? (
          <Card>
            <CardContent className="p-6 text-sm text-muted-foreground">
              No research runs yet. Start a workflow above and completed reports will appear here.
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {runs.slice(0, 3).map((run) => (
            <Card key={run.id} className="transition-transform hover:-translate-y-0.5">
              <CardHeader>
                <div className="flex items-start justify-between gap-3">
                  <CardTitle className="line-clamp-2 text-base">{run.prompt}</CardTitle>
                  <Badge status={run.status}>{run.status}</Badge>
                </div>
                <CardDescription>{new Date(run.createdAt).toLocaleString()} · {run.depth}</CardDescription>
              </CardHeader>
              <CardContent>
                <Progress value={run.progress} />
                <div className="mt-4 flex justify-between">
                  <Button variant="outline" size="sm" onClick={() => router.push(`/execution/${run.id}`)}>Open workflow</Button>
                  <Button variant="ghost" size="sm" onClick={() => router.push(`/reports/${run.id}`)}>Report</Button>
                </div>
              </CardContent>
            </Card>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
