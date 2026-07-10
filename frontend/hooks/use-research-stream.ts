"use client";

import { useEffect } from "react";
import { researchApi } from "@/services/api";
import { useResearchStore } from "@/store/research-store";
import type { StreamEvent } from "@/types/research";

const MAX_RETRIES = 5;

export function useResearchStream(runId?: string) {
  const updateActiveRun = useResearchStore((state) => state.updateActiveRun);
  const addLog = useResearchStore((state) => state.addLog);
  const upsertTool = useResearchStore((state) => state.upsertTool);
  const setReport = useResearchStore((state) => state.setReport);
  const pushToast = useResearchStore((state) => state.pushToast);

  useEffect(() => {
    if (!runId) return;

    let source: EventSource | null = null;
    let retries = 0;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;
    let finished = false;
    let disposed = false;

    const connect = () => {
      if (disposed) return;
      source = new EventSource(researchApi.streamUrl(runId));

      source.onopen = () => {
        retries = 0;
      };

      source.onmessage = (message) => {
        const event = JSON.parse(message.data) as StreamEvent;
        if (event.run) updateActiveRun(event.run);
        if (event.log) addLog(event.log);
        if (event.tool) upsertTool(event.tool);
        if (event.report) setReport(event.report);
        if (event.type === "complete") {
          finished = true;
          pushToast({ title: "Research complete", description: "The final report is ready.", tone: "success" });
          source?.close();
        }
        if (event.type === "error") {
          finished = true;
          pushToast({ title: "Research interrupted", description: event.message, tone: "error" });
          source?.close();
        }
      };

      source.onerror = () => {
        source?.close();
        if (finished || disposed) return;
        if (retries >= MAX_RETRIES) {
          pushToast({
            title: "Live stream disconnected",
            description: "Could not reconnect. Refresh the page to resume.",
            tone: "error",
          });
          return;
        }
        const delay = Math.min(1000 * 2 ** retries, 15000);
        retries += 1;
        pushToast({
          title: "Live stream interrupted",
          description: `Reconnecting (attempt ${retries}/${MAX_RETRIES})…`,
          tone: "default",
        });
        retryTimer = setTimeout(connect, delay);
      };
    };

    connect();

    return () => {
      disposed = true;
      if (retryTimer) clearTimeout(retryTimer);
      source?.close();
    };
  }, [addLog, pushToast, runId, setReport, updateActiveRun, upsertTool]);
}
