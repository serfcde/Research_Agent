"use client";

import { Bell, KeyRound, Moon, User } from "lucide-react";
import { useTheme } from "next-themes";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Switch } from "@/components/ui/form";
import { useResearchStore } from "@/store/research-store";

export default function SettingsPage() {
  const { resolvedTheme, setTheme } = useTheme();
  const settings = useResearchStore((state) => state.settings);
  const updateSettings = useResearchStore((state) => state.updateSettings);
  const pushToast = useResearchStore((state) => state.pushToast);

  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <div>
        <h1 className="text-2xl font-semibold">Settings</h1>
        <p className="mt-1 text-sm text-muted-foreground">Configure workspace preferences, API routing, notifications, and profile details.</p>
      </div>

      <Card>
        <CardHeader><CardTitle className="flex items-center gap-2"><Moon className="h-5 w-5 text-primary" />Appearance</CardTitle><CardDescription>Theme and interface preferences.</CardDescription></CardHeader>
        <CardContent className="flex items-center justify-between">
          <div><p className="text-sm font-medium">Dark mode</p><p className="text-sm text-muted-foreground">Use the futuristic dashboard theme.</p></div>
          <Switch checked={resolvedTheme === "dark"} onCheckedChange={(checked) => setTheme(checked ? "dark" : "light")} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="flex items-center gap-2"><KeyRound className="h-5 w-5 text-primary" />API Configuration</CardTitle><CardDescription>Frontend mock routes and backend service targets.</CardDescription></CardHeader>
        <CardContent className="grid gap-4">
          <div className="space-y-2">
            <Label>Frontend API base URL</Label>
            <Input value={settings.apiBaseUrl} onChange={(event) => updateSettings({ apiBaseUrl: event.target.value })} />
          </div>
          <div className="space-y-2">
            <Label>Backend API URL</Label>
            <Input value={settings.backendApiUrl} onChange={(event) => updateSettings({ backendApiUrl: event.target.value })} />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="flex items-center gap-2"><Bell className="h-5 w-5 text-primary" />Notifications</CardTitle><CardDescription>Control workflow alerts and completion actions.</CardDescription></CardHeader>
        <CardContent className="space-y-4">
          <SettingToggle title="Completion notifications" description="Show a toast when a research report is ready." checked={settings.notifications} onCheckedChange={(notifications) => updateSettings({ notifications })} />
          <SettingToggle title="Auto-download TXT" description="Download reports automatically after formatting." checked={settings.autoDownload} onCheckedChange={(autoDownload) => updateSettings({ autoDownload })} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="flex items-center gap-2"><User className="h-5 w-5 text-primary" />User Profile</CardTitle><CardDescription>Authentication UI for the research workspace.</CardDescription></CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2"><Label>Name</Label><Input value={settings.profileName} onChange={(event) => updateSettings({ profileName: event.target.value })} /></div>
          <div className="space-y-2"><Label>Email</Label><Input value={settings.profileEmail} onChange={(event) => updateSettings({ profileEmail: event.target.value })} /></div>
          <div className="sm:col-span-2"><Button onClick={() => pushToast({ title: "Settings saved", description: "Workspace preferences updated.", tone: "success" })}>Save settings</Button></div>
        </CardContent>
      </Card>
    </div>
  );
}

function SettingToggle({ title, description, checked, onCheckedChange }: { title: string; description: string; checked: boolean; onCheckedChange: (checked: boolean) => void }) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-lg border border-border bg-background/35 p-4">
      <div><p className="text-sm font-medium">{title}</p><p className="text-sm text-muted-foreground">{description}</p></div>
      <Switch checked={checked} onCheckedChange={onCheckedChange} />
    </div>
  );
}
