"use client";

import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

interface State {
  hasError: boolean;
}

export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(error, info);
  }

  render() {
    if (!this.state.hasError) return this.props.children;
    return (
      <div className="glass flex min-h-80 flex-col items-center justify-center rounded-lg p-8 text-center">
        <AlertTriangle className="h-10 w-10 text-destructive" />
        <h2 className="mt-4 text-xl font-semibold">Something interrupted the workspace</h2>
        <p className="mt-2 max-w-md text-sm text-muted-foreground">The dashboard hit an unexpected rendering issue. Retry to reload the current view.</p>
        <Button className="mt-5" onClick={() => this.setState({ hasError: false })}>
          <RefreshCw className="h-4 w-4" />
          Retry
        </Button>
      </div>
    );
  }
}
