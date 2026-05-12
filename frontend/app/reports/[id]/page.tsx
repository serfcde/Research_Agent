"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { ReportViewer } from "@/components/research/report-viewer";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { researchApi } from "@/services/api";
import { useResearchStore } from "@/store/research-store";
import type { ResearchReport } from "@/types/research";

export default function ReportPage() {
  const params = useParams<{ id: string }>();
  const [report, setReport] = useState<ResearchReport | undefined>();
  const [notReady, setNotReady] = useState(false);
  const pushToast = useResearchStore((state) => state.pushToast);

  useEffect(() => {
    researchApi.report(params.id).then((nextReport) => {
      setReport(nextReport);
      setNotReady(false);
    }).catch(() => {
      setNotReady(true);
      pushToast({ title: "Report is not ready", description: "Wait for the backend formatter step to finish.", tone: "error" });
    });
  }, [params.id, pushToast]);

  if (notReady) {
    return (
      <Card>
        <CardContent className="p-8 text-center">
          <h1 className="text-xl font-semibold">Report is not ready yet</h1>
          <p className="mt-2 text-sm text-muted-foreground">The frontend now waits for the real backend Formatter Agent. Return to the live execution view and open the report after completion.</p>
        </CardContent>
      </Card>
    );
  }

  if (!report) {
    return <div className="space-y-4"><Skeleton className="h-16" /><Skeleton className="h-64" /><Skeleton className="h-64" /></div>;
  }

  return <ReportViewer report={report} />;
}
