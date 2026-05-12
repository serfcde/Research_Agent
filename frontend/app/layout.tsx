import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "@/components/providers";
import { AppShell } from "@/components/layout/app-shell";
import { ToastViewport } from "@/components/ui/toast";

export const metadata: Metadata = {
  title: "Agentic Research System",
  description: "AI-powered multi-agent research workflow dashboard"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="font-sans">
        <Providers>
          <AppShell>{children}</AppShell>
          <ToastViewport />
        </Providers>
      </body>
    </html>
  );
}
