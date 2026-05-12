"use client";

import { X } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { useResearchStore } from "@/store/research-store";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function ToastViewport() {
  const toasts = useResearchStore((state) => state.toasts);
  const dismissToast = useResearchStore((state) => state.dismissToast);

  return (
    <div className="fixed bottom-4 right-4 z-50 flex w-[calc(100%-2rem)] max-w-sm flex-col gap-3">
      <AnimatePresence>
        {toasts.map((toast) => (
          <motion.div
            key={toast.id}
            initial={{ opacity: 0, y: 16, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 16, scale: 0.96 }}
            className={cn("glass rounded-lg p-4", toast.tone === "error" && "border-red-500/30", toast.tone === "success" && "border-emerald-400/30")}
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold">{toast.title}</p>
                {toast.description ? <p className="mt-1 text-sm text-muted-foreground">{toast.description}</p> : null}
              </div>
              <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => dismissToast(toast.id)} aria-label="Dismiss notification">
                <X className="h-4 w-4" />
              </Button>
            </div>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
