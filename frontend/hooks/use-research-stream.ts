"use client";

import { useEffect } from "react";
import { researchApi } from "@/services/api";
import { useResearchStore } from "@/store/research-store";
import type { StreamEvent } from "@/types/research";

export function useResearchStream(runId?: string) {
  const updateActiveRun = useResearchStore((state) => state.updateActiveRun);
  const addLog = useResearchStore((state) => state.addLog);
  const upsertTool = useResearchStore((state) => state.upsertTool);
  const setReport = useResearchStore((state) => state.setReport);
  const pushToast = useResearchStore((state) => state.pushToast);

  useEffect(() => {
    if (!runId) return;
    const source = new EventSource(researchApi.streamUrl(runId));

    source.onmessage = (message) => {
      const event = JSON.parse(message.data) as StreamEvent;
      if (event.run) updateActiveRun(event.run);
      if (event.log) addLog(event.log);
      if (event.tool) upsertTool(event.tool);
      if (event.report) setReport(event.report);
      if (event.type === "complete") {
        pushToast({ title: "Research complete", description: "The final report is ready.", tone: "success" });
        source.close();
      }
      if (event.type === "error") {
        pushToast({ title: "Research interrupted", description: event.message, tone: "error" });
      }
    };

    source.onerror = () => {
      pushToast({ title: "Live stream disconnected", description: "Retrying status sync in the background.", tone: "error" });
      source.close();
    };

    return () => source.close();
  }, [addLog, pushToast, runId, setReport, updateActiveRun, upsertTool]);
}
