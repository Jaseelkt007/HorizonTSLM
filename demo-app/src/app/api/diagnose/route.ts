import { execFile } from "child_process";
import path from "path";
import { promisify } from "util";
import { NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const execFileAsync = promisify(execFile);
const repoRoot = process.env.TURBINE_TSLM_ROOT
  ?? path.resolve(process.cwd(), path.basename(process.cwd()) === "demo-app" ? ".." : ".");

export async function POST(request: Request) {
  const body: unknown = await request.json().catch(() => null);
  if (!body || typeof body !== "object") return NextResponse.json({ error: "Invalid request body." }, { status: 400 });
  const { sourceWindowId, question } = body as { sourceWindowId?: unknown; question?: unknown };
  if (typeof sourceWindowId !== "string" || typeof question !== "string" || !sourceWindowId || !question.trim()) return NextResponse.json({ error: "sourceWindowId and question are required." }, { status: 400 });
  try {
    const { stdout } = await execFileAsync("uv", ["run", "python", "-m", "turbine_tslm.demo.infer", "--window-id", sourceWindowId, "--question", question.trim()], { cwd: repoRoot, timeout: 10 * 60 * 1000, maxBuffer: 1024 * 1024, env: process.env });
    // The Python model loader can emit progress lines before its final JSON.
    const jsonLine = stdout.trim().split("\n").at(-1) ?? "";
    const result = JSON.parse(jsonLine) as { answer?: string };
    if (!result.answer) throw new Error("Inference returned no answer.");
    return NextResponse.json({ answer: result.answer });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Inference failed.";
    return NextResponse.json({ error: message.slice(0, 1000) }, { status: 503 });
  }
}
