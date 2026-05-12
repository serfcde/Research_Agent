"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import { ChevronDown, Clipboard, Download, FileDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { researchApi } from "@/services/api";
import { useResearchStore } from "@/store/research-store";
import type { ResearchReport } from "@/types/research";
import { cn } from "@/lib/utils";

export function ReportViewer({ report }: { report: ResearchReport }) {
  const [openSections, setOpenSections] = useState<Record<string, boolean>>(
    Object.fromEntries([...report.topics, "Comparative Analysis", "Key Insights", "Conclusion"].map((section) => [section, true]))
  );
  const pushToast = useResearchStore((state) => state.pushToast);

  const markdown = [
    `# ${report.title}`,
    report.introduction,
    ...Object.entries(report.sections).map(([title, content]) => `## ${title}\n${content}`),
    `## Comparative Analysis\n${report.comparativeAnalysis}`,
    `## Key Insights\n${report.keyInsights.map((insight) => `- ${insight}`).join("\n")}`,
    `## Conclusion\n${report.conclusion}`
  ].join("\n\n");

  async function copyReport() {
    await navigator.clipboard.writeText(markdown);
    pushToast({ title: "Report copied", description: "Markdown copied to clipboard.", tone: "success" });
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
        <div>
          <h1 className="text-2xl font-semibold tracking-normal">{report.title}</h1>
          <p className="mt-1 text-sm text-muted-foreground">{report.totalWords.toLocaleString()} words · {new Date(report.generatedAt).toLocaleString()}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={copyReport}><Clipboard className="h-4 w-4" />Copy</Button>
          <Button variant="outline" asChild><a href={researchApi.downloadUrl(report.id)}><Download className="h-4 w-4" />TXT</a></Button>
          <Button><FileDown className="h-4 w-4" />Export</Button>
        </div>
      </div>

      <Card>
        <CardContent className="p-5">
          <ReactMarkdown className="prose prose-sm max-w-none dark:prose-invert prose-headings:tracking-normal prose-a:text-primary">
            {`## Executive Summary\n${report.introduction}`}
          </ReactMarkdown>
        </CardContent>
      </Card>

      {Object.entries(report.sections).map(([title, content]) => (
        <CollapsibleSection key={title} title={title} open={openSections[title]} onToggle={() => setOpenSections((state) => ({ ...state, [title]: !state[title] }))}>
          <ReactMarkdown className="prose prose-sm max-w-none dark:prose-invert">{content}</ReactMarkdown>
        </CollapsibleSection>
      ))}

      <CollapsibleSection title="Comparative Analysis" open={openSections["Comparative Analysis"]} onToggle={() => setOpenSections((state) => ({ ...state, "Comparative Analysis": !state["Comparative Analysis"] }))}>
        <p className="text-sm leading-7 text-muted-foreground">{report.comparativeAnalysis}</p>
      </CollapsibleSection>

      <CollapsibleSection title="Key Insights" open={openSections["Key Insights"]} onToggle={() => setOpenSections((state) => ({ ...state, "Key Insights": !state["Key Insights"] }))}>
        <ul className="grid gap-3 sm:grid-cols-2">
          {report.keyInsights.map((insight) => <li key={insight} className="rounded-md border border-border bg-background/40 p-3 text-sm">{insight}</li>)}
        </ul>
      </CollapsibleSection>

      <CollapsibleSection title="Conclusion" open={openSections.Conclusion} onToggle={() => setOpenSections((state) => ({ ...state, Conclusion: !state.Conclusion }))}>
        <p className="text-sm leading-7 text-muted-foreground">{report.conclusion}</p>
      </CollapsibleSection>
    </div>
  );
}

function CollapsibleSection({ title, open, onToggle, children }: { title: string; open: boolean; onToggle: () => void; children: React.ReactNode }) {
  return (
    <Card>
      <CardHeader className="cursor-pointer select-none" onClick={onToggle}>
        <div className="flex items-center justify-between">
          <CardTitle>{title}</CardTitle>
          <ChevronDown className={cn("h-5 w-5 text-muted-foreground transition-transform", open && "rotate-180")} />
        </div>
      </CardHeader>
      {open ? <CardContent>{children}</CardContent> : null}
    </Card>
  );
}
