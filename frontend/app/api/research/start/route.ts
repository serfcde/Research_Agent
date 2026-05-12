import { NextResponse } from "next/server";
import { createRun, postBackend } from "@/lib/server/research-registry";
import type { StartResearchPayload, ResearchReport } from "@/types/research";

export async function POST(request: Request) {
  try {
    const body = (await request.json()) as StartResearchPayload;
    
    // Create local run immediately
    const run = createRun(body.prompt, body.depth);
    
    // Fire off backend research in the background
    // Don't wait for it - return run immediately for better UX
    postBackend<ResearchReport>("/api/research", {
      prompt: body.prompt,
      depth: body.depth
    }).catch(error => {
      console.error("Backend research failed:", error);
    });
    
    return NextResponse.json(run);
  } catch (error) {
    console.error("Start research error:", error);
    return NextResponse.json(
      { error: "Failed to start research" },
      { status: 500 }
    );
  }
}
