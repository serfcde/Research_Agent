import { cn } from "@/lib/utils";
import type { AgentStatus } from "@/types/research";

const statusClasses: Record<AgentStatus, string> = {
  idle: "bg-muted text-muted-foreground",
  queued: "bg-blue-500/15 text-blue-300",
  running: "bg-primary/15 text-primary",
  completed: "bg-emerald-500/15 text-emerald-300",
  failed: "bg-destructive/15 text-red-300"
};

export function Badge({ className, status, children }: { className?: string; status?: AgentStatus; children: React.ReactNode }) {
  return <span className={cn("inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium", status ? statusClasses[status] : "bg-muted", className)}>{children}</span>;
}
