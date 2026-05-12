"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BarChart3, Bot, Clock3, FileText, History, Home, Menu, Moon, Search, Settings, Shield, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/form";
import { cn, initials } from "@/lib/utils";
import { ErrorBoundary } from "@/components/error-boundary";

const nav = [
  { href: "/", label: "Dashboard", icon: Home },
  { href: "/", label: "Live Execution", icon: Bot },
  { href: "/reports/ars-20260511-qc-edge", label: "Reports", icon: FileText },
  { href: "/history", label: "History", icon: History },
  { href: "/settings", label: "Settings", icon: Settings }
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { resolvedTheme, setTheme } = useTheme();

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[280px_1fr]">
      <aside className="sticky top-0 z-30 hidden h-screen border-r border-border/70 bg-background/70 backdrop-blur-xl lg:block">
        <div className="flex h-full flex-col">
          <Link href="/" className="flex items-center gap-3 px-6 py-6">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br from-primary to-accent text-primary-foreground shadow-glow">
              <Bot className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm font-semibold leading-none">Agentic Research</p>
              <p className="mt-1 text-xs text-muted-foreground">System Console</p>
            </div>
          </Link>
          <nav className="space-y-1 px-3">
            {nav.map((item) => {
              const active = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href.split("/")[1] ? `/${item.href.split("/")[1]}` : item.href));
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "flex items-center gap-3 rounded-md px-3 py-2.5 text-sm text-muted-foreground transition-colors hover:bg-muted/70 hover:text-foreground",
                    active && "bg-primary/12 text-primary"
                  )}
                >
                  <Icon className="h-4 w-4" />
                  {item.label}
                </Link>
              );
            })}
          </nav>
          <div className="mt-auto p-4">
            <div className="glass rounded-lg p-4">
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-md bg-muted text-xs font-semibold">DR</div>
                <div>
                  <p className="text-sm font-medium">Divya Research</p>
                  <p className="text-xs text-muted-foreground">Pro workspace</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </aside>
      <div className="min-w-0">
        <header className="sticky top-0 z-20 border-b border-border/70 bg-background/70 backdrop-blur-xl">
          <div className="flex h-16 items-center gap-3 px-4 sm:px-6">
            <Button variant="ghost" size="icon" className="lg:hidden" aria-label="Open navigation">
              <Menu className="h-5 w-5" />
            </Button>
            <div className="hidden min-w-0 max-w-md flex-1 items-center gap-2 rounded-md border border-border bg-background/50 px-3 md:flex">
              <Search className="h-4 w-4 text-muted-foreground" />
              <Input className="h-9 border-0 bg-transparent px-0 focus-visible:ring-0 focus-visible:ring-offset-0" placeholder="Search reports, sources, tasks..." />
            </div>
            <div className="ml-auto flex items-center gap-2">
              <div className="hidden items-center gap-2 rounded-md border border-border bg-background/50 px-3 py-2 text-xs text-muted-foreground sm:flex">
                <Clock3 className="h-4 w-4 text-primary" />
                Live API ready
              </div>
              <div className="hidden items-center gap-2 rounded-md border border-border bg-background/50 px-3 py-2 text-xs text-muted-foreground xl:flex">
                <BarChart3 className="h-4 w-4 text-accent" />
                23k tokens/session
              </div>
              <Button variant="outline" size="icon" onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")} aria-label="Toggle theme">
                {resolvedTheme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
              </Button>
              <Link href="/login" className="flex h-10 w-10 items-center justify-center rounded-md bg-muted text-xs font-semibold" aria-label="Open authentication">
                {initials("Divya Research")}
              </Link>
            </div>
          </div>
        </header>
        <main className="px-4 py-6 sm:px-6 lg:px-8">
          <ErrorBoundary>{children}</ErrorBoundary>
        </main>
      </div>
    </div>
  );
}
