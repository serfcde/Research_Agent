"use client";

import { Bot, Github, Mail } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/form";

export default function LoginPage() {
  return (
    <div className="mx-auto grid min-h-[calc(100vh-8rem)] max-w-5xl items-center gap-8 lg:grid-cols-[0.9fr_1.1fr]">
      <div>
        <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-gradient-to-br from-primary to-accent text-primary-foreground shadow-glow"><Bot className="h-6 w-6" /></div>
        <h1 className="mt-6 text-3xl font-semibold">Secure research operations for AI teams.</h1>
        <p className="mt-3 text-muted-foreground">Authentication UI prepared for SSO, audit-ready research history, and workspace-level API controls.</p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Sign in</CardTitle>
          <CardDescription>Access the Agentic Research System workspace.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2"><Label>Email</Label><Input placeholder="divya@example.com" type="email" /></div>
          <div className="space-y-2"><Label>Password</Label><Input placeholder="••••••••" type="password" /></div>
          <Button className="w-full"><Mail className="h-4 w-4" />Continue with email</Button>
          <Button variant="outline" className="w-full"><Github className="h-4 w-4" />Continue with SSO</Button>
        </CardContent>
      </Card>
    </div>
  );
}
