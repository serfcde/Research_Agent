import type { ActivityLog } from "@/types/research";
import { cn } from "@/lib/utils";

const levelClass = {
  info: "text-blue-300",
  success: "text-emerald-300",
  warning: "text-amber-300",
  error: "text-red-300",
  tool: "text-primary"
};

export function LiveLogs({ logs }: { logs: ActivityLog[] }) {
  return (
    <div className="h-[360px] overflow-y-auto rounded-lg border border-border bg-slate-950 p-4 font-mono text-xs text-slate-200 shadow-inner">
      {logs.length === 0 ? (
        <div className="flex h-full items-center justify-center text-slate-500">Waiting for agent telemetry...</div>
      ) : (
        <div className="space-y-2">
          {logs.map((log) => (
            <div key={log.id} className="grid grid-cols-[86px_96px_1fr] gap-3">
              <span className="text-slate-500">{new Date(log.timestamp).toLocaleTimeString()}</span>
              <span className={cn("uppercase", levelClass[log.level])}>{log.agent}</span>
              <span>{log.message}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
