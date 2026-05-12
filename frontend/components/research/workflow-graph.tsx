"use client";

import { motion } from "framer-motion";
import { Bot, FileText, ListChecks, Search, WandSparkles } from "lucide-react";
import type { AgentNode } from "@/types/research";
import { cn } from "@/lib/utils";

const nodeIcons = [WandSparkles, ListChecks, Bot, Search, FileText];

export function WorkflowGraph({ agents }: { agents: AgentNode[] }) {
  return (
    <div className="overflow-x-auto pb-2">
      <div className="relative flex min-w-[760px] items-center justify-between gap-4 rounded-lg border border-border bg-background/35 p-5">
        <div className="absolute left-12 right-12 top-1/2 h-px bg-border" />
        <motion.div className="absolute left-12 top-1/2 h-px bg-gradient-to-r from-primary to-accent" initial={{ width: "0%" }} animate={{ width: `${Math.max(8, Math.min(82, agents.reduce((sum, agent) => sum + agent.progress, 0) / agents.length))}%` }} transition={{ duration: 0.8 }} />
        {agents.map((agent, index) => {
          const Icon = nodeIcons[index] || Bot;
          return (
            <div key={agent.id} className="relative z-10 flex flex-col items-center text-center">
              <motion.div
                animate={agent.status === "running" ? { scale: [1, 1.08, 1] } : { scale: 1 }}
                transition={{ repeat: agent.status === "running" ? Infinity : 0, duration: 1.4 }}
                className={cn(
                  "flex h-14 w-14 items-center justify-center rounded-lg border bg-card shadow-glass",
                  agent.status === "completed" && "border-emerald-400/40 text-emerald-300",
                  agent.status === "running" && "border-primary/50 text-primary shadow-glow",
                  agent.status === "failed" && "border-red-400/50 text-red-300"
                )}
              >
                <Icon className="h-6 w-6" />
              </motion.div>
              <p className="mt-3 text-xs font-medium">{agent.name}</p>
              <p className="mt-1 text-[11px] text-muted-foreground">{agent.progress}%</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
