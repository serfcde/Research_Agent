import { NextResponse } from "next/server";
import { createRun } from "@/lib/server/research-registry";
import type { StartResearchPayload } from "@/types/research";

export async function POST(request: Request) {
  const body = (await request.json()) as StartResearchPayload;
  const run = createRun(body.prompt, body.depth);
  return NextResponse.json(run);
}
