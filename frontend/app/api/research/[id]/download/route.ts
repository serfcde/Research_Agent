import { getRun, reportToText } from "@/lib/server/research-registry";

export async function GET(_: Request, { params }: { params: { id: string } }) {
  const report = getRun(params.id)?.report;
  if (!report) return new Response("Report not ready", { status: 404 });

  return new Response(reportToText(report), {
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "Content-Disposition": `attachment; filename="${report.id}.txt"`
    }
  });
}
