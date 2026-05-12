"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { ActivityLog, ResearchReport, ResearchRun, SettingsState, ToolExecution } from "@/types/research";

interface Toast {
  id: string;
  title: string;
  description?: string;
  tone?: "default" | "success" | "error";
}

interface ResearchStore {
  runs: ResearchRun[];
  activeRun?: ResearchRun;
  report?: ResearchReport;
  settings: SettingsState;
  toasts: Toast[];
  setRuns: (runs: ResearchRun[]) => void;
  setActiveRun: (run: ResearchRun) => void;
  updateActiveRun: (run: Partial<ResearchRun>) => void;
  addLog: (log: ActivityLog) => void;
  upsertTool: (tool: ToolExecution) => void;
  setReport: (report: ResearchReport) => void;
  updateSettings: (settings: Partial<SettingsState>) => void;
  pushToast: (toast: Omit<Toast, "id">) => void;
  dismissToast: (id: string) => void;
}

export const useResearchStore = create<ResearchStore>()(
  persist(
    (set) => ({
      runs: [],
      settings: {
        apiBaseUrl: process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:3000",
        backendApiUrl: process.env.NEXT_PUBLIC_BACKEND_API_URL || "http://127.0.0.1:8001",
        notifications: true,
        autoDownload: false,
        profileName: "Divya Research",
        profileEmail: "divya@example.com"
      },
      toasts: [],
      setRuns: (runs) => set({ runs }),
      setActiveRun: (run) =>
        set((state) => ({
          activeRun: run,
          runs: [run, ...state.runs.filter((item) => item.id !== run.id)]
        })),
      updateActiveRun: (run) =>
        set((state) => {
          if (!state.activeRun) return state;
          const nextRun = { ...state.activeRun, ...run };
          return {
            activeRun: nextRun,
            runs: state.runs.map((item) => (item.id === nextRun.id ? nextRun : item))
          };
        }),
      addLog: (log) =>
        set((state) => {
          if (!state.activeRun) return state;
          const nextRun = { ...state.activeRun, logs: [...state.activeRun.logs, log] };
          return {
            activeRun: nextRun,
            runs: state.runs.map((item) => (item.id === nextRun.id ? nextRun : item))
          };
        }),
      upsertTool: (tool) =>
        set((state) => {
          if (!state.activeRun) return state;
          const tools = [...state.activeRun.tools.filter((item) => item.id !== tool.id), tool];
          const nextRun = { ...state.activeRun, tools };
          return {
            activeRun: nextRun,
            runs: state.runs.map((item) => (item.id === nextRun.id ? nextRun : item))
          };
        }),
      setReport: (report) =>
        set((state) => {
          const activeRun = state.activeRun ? { ...state.activeRun, report, status: "completed" as const, progress: 100 } : state.activeRun;
          return {
            report,
            activeRun,
            runs: activeRun ? state.runs.map((item) => (item.id === activeRun.id ? activeRun : item)) : state.runs
          };
        }),
      updateSettings: (settings) => set((state) => ({ settings: { ...state.settings, ...settings } })),
      pushToast: (toast) =>
        set((state) => ({
          toasts: [...state.toasts, { ...toast, id: crypto.randomUUID() }]
        })),
      dismissToast: (id) => set((state) => ({ toasts: state.toasts.filter((toast) => toast.id !== id) }))
    }),
    {
      name: "agentic-research-system-v2",
      partialize: (state) => ({ runs: state.runs, settings: state.settings })
    }
  )
);
