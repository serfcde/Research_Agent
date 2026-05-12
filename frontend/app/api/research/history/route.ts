import { NextResponse } from "next/server";
import { listRuns } from "@/lib/server/research-registry";

export async function GET() {
  return NextResponse.json(listRuns());
}
