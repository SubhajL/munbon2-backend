import { type NextRequest, type NextResponse } from "next/server";
import { proxyLogout } from "@/lib/auth-proxy";
import { readRefreshCookie, toNextResponse } from "@/lib/auth-route";

export async function POST(req: NextRequest): Promise<NextResponse> {
  return toNextResponse(await proxyLogout(readRefreshCookie(req)));
}
