"use client";

// components/research/workflow-graph.tsx
// Clickable nodes — clicking opens NodeDetailPanel with prompt/output

import { useState } from "react";
import { motion } from "framer-motion";
import { Bot, FileText, Search, Sparkles, ListTodo } from "lucide-react";
import { AgentNode, AgentStep } from "@/types/research";
import { NodeDetailPanel } from "./node-detail-panel";
import { Card, CardContent } from "@/components/ui/card";

const nodeIcons = [Sparkles, ListTodo, Bot, Search, FileText];

interface WorkflowGraphProps {
  agents?: AgentNode[];
  steps?: AgentStep[];
}

export function WorkflowGraph({ agents = [], steps = [] }: WorkflowGraphProps) {
  const [selectedStep, setSelectedStep] = useState<AgentStep | null>(null);

  // Find matching step for an agent
  const findStep = (agentId: string): AgentStep | undefined =>
    steps.find((s) => s.agentId === agentId);

  const handleNodeClick = (agent: AgentNode) => {
    const step = findStep(agent.id);
    if (step) setSelectedStep(step);
  };

  return (
    <>
      <Card>
        <CardContent className="overflow-x-auto p-5">
          <div className="relative flex min-w-[760px] items-center justify-between gap-4 rounded-lg border border-border bg-background/35 p-5">
            {/* Progress line background */}
            <div className="absolute left-12 right-12 top-1/2 h-px bg-border" />

            {/* Animated progress line */}
            <motion.div
              className="absolute left-12 top-1/2 h-px bg-gradient-to-r from-primary to-accent"
              initial={{ width: "0%" }}
              animate={{
                width: `${Math.max(
                  8,
                  Math.min(
                    82,
                    (agents ?? []).reduce((sum, a) => sum + a.progress, 0) /
                      Math.max((agents ?? []).length, 1)
                  )
                )}%`,
              }}
              transition={{ duration: 0.8 }}
            />

            {/* Agent nodes */}
            {(agents ?? []).map((agent, index) => {
              const Icon = nodeIcons[index] || Bot;
              const step = findStep(agent.id);
              const isClickable = !!step;

              return (
                <div
                  key={agent.id}
                  className={`relative z-10 flex flex-col items-center gap-2 ${
                    isClickable
                      ? "cursor-pointer group"
                      : "cursor-default"
                  }`}
                  onClick={() => handleNodeClick(agent)}
                  title={isClickable ? `Click to inspect ${agent.name}` : agent.name}
                >
                  {/* Node circle */}
                  <div
                    className={`
                      flex h-11 w-11 items-center justify-center rounded-full border-2 transition-all duration-200
                      ${agent.status === "completed"
                        ? "border-primary bg-primary/20 text-primary"
                        : agent.status === "running"
                        ? "border-accent bg-accent/20 text-accent animate-pulse"
                        : agent.status === "failed"
                        ? "border-destructive bg-destructive/20 text-destructive"
                        : "border-muted-foreground/30 bg-muted/20 text-muted-foreground"
                      }
                      ${isClickable ? "group-hover:scale-110 group-hover:shadow-lg group-hover:shadow-primary/20" : ""}
                    `}
                  >
                    <Icon className="h-5 w-5" />
                  </div>

                  {/* Agent name */}
                  <span className="text-center text-xs font-medium leading-tight max-w-[80px]">
                    {agent.name}
                  </span>

                  {/* Progress */}
                  <span className="text-xs text-muted-foreground">{agent.progress}%</span>

                  {/* "Click to inspect" hint */}
                  {isClickable && (
                    <span className="absolute -bottom-6 text-[10px] text-primary opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">
                      Click to inspect
                    </span>
                  )}
                </div>
              );
            })}
          </div>

          {/* Steps summary below graph */}
          {steps.length > 0 && (
            <div className="mt-4 flex flex-wrap gap-2">
              {steps
                .filter((s) => !s.agentId.startsWith("tool-search"))
                .map((step) => (
                  <button
                    key={step.agentId}
                    onClick={() => setSelectedStep(step)}
                    className="rounded-full border border-border bg-muted/30 px-3 py-1 text-xs hover:bg-muted hover:text-primary transition-colors"
                  >
                    {step.agentName}
                    {step.durationMs && (
                      <span className="ml-1.5 text-muted-foreground">
                        {step.durationMs > 1000
                          ? `${(step.durationMs / 1000).toFixed(1)}s`
                          : `${step.durationMs}ms`}
                      </span>
                    )}
                  </button>
                ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Detail panel */}
      {selectedStep && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-40 bg-background/60 backdrop-blur-sm"
            onClick={() => setSelectedStep(null)}
          />
          <NodeDetailPanel
            step={selectedStep}
            onClose={() => setSelectedStep(null)}
          />
        </>
      )}
    </>
  );
}
