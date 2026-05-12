"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Download, FileText, Search } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/form";
import { researchApi } from "@/services/api";
import { useResearchStore } from "@/store/research-store";

export default function HistoryPage() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const runs = useResearchStore((state) => state.runs);
  const setRuns = useResearchStore((state) => state.setRuns);

  useEffect(() => {
    researchApi.history().then(setRuns).catch(() => undefined);
  }, [setRuns]);

  const filtered = useMemo(() => {
    return runs.filter((run) => {
      const matchesQuery = `${run.prompt} ${run.report?.topics.join(" ")}`.toLowerCase().includes(query.toLowerCase());
      const matchesFilter = filter === "all" || run.depth === filter || run.status === filter;
      return matchesQuery && matchesFilter;
    });
  }, [filter, query, runs]);

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold">Research History</h1>
        <p className="mt-1 text-sm text-muted-foreground">Search, filter, reopen, and download previous reports.</p>
      </div>
      <Card>
        <CardContent className="grid gap-3 p-4 md:grid-cols-[1fr_220px]">
          <div className="flex items-center gap-2 rounded-md border border-border bg-background/50 px-3">
            <Search className="h-4 w-4 text-muted-foreground" />
            <Input className="border-0 bg-transparent px-0 focus-visible:ring-0 focus-visible:ring-offset-0" placeholder="Search by topic or prompt" value={query} onChange={(event) => setQuery(event.target.value)} />
          </div>
          <Select value={filter} onValueChange={setFilter}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All reports</SelectItem>
              <SelectItem value="quick">Quick</SelectItem>
              <SelectItem value="medium">Medium</SelectItem>
              <SelectItem value="deep">Deep</SelectItem>
              <SelectItem value="completed">Completed</SelectItem>
              <SelectItem value="running">Running</SelectItem>
            </SelectContent>
          </Select>
        </CardContent>
      </Card>
      <div className="grid gap-4">
        {filtered.map((run) => (
          <Card key={run.id}>
            <CardHeader>
              <div className="flex flex-col justify-between gap-3 md:flex-row md:items-start">
                <div>
                  <CardTitle>{run.prompt}</CardTitle>
                  <p className="mt-1 text-sm text-muted-foreground">{new Date(run.createdAt).toLocaleString()} · {run.depth} depth</p>
                </div>
                <Badge status={run.status}>{run.status}</Badge>
              </div>
            </CardHeader>
            <CardContent className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
              <div className="flex flex-wrap gap-2">
                {run.report?.topics.map((topic) => <span key={topic} className="rounded-full bg-muted px-2.5 py-1 text-xs text-muted-foreground">{topic}</span>)}
              </div>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={() => router.push(`/reports/${run.id}`)}><FileText className="h-4 w-4" />Re-open</Button>
                <Button variant="ghost" size="sm" asChild><a href={researchApi.downloadUrl(run.id)}><Download className="h-4 w-4" />TXT</a></Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
