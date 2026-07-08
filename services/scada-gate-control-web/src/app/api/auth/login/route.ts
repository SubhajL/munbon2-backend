import { NextResponse, type NextRequest } from "next/server";
import { proxyLogin } from "@/lib/auth-proxy";
import { toNextResponse } from "@/lib/auth-route";

export async function POST(req: NextRequest): Promise<NextResponse> {
  const body = (await req.json().catch(() => ({}))) as {
    email?: unknown;
    password?: unknown;
  };
  if (typeof body.email !== "string" || typeof body.password !== "string") {
    return NextResponse.json(
      { error: "Email and password are required" },
      { status: 400 },
    );
  }
  return toNextResponse(
    await proxyLogin({ email: body.email, password: body.password }),
  );
}
