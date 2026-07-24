import { NextResponse, type NextRequest } from "next/server";

const UPSTREAM_TIMEOUT_MS = 5_000;

type RouteContext = {
  params: Promise<{ id: string }>;
};

function noStore(body: unknown, status: number): NextResponse {
  return NextResponse.json(body, {
    status,
    headers: { "Cache-Control": "no-store" },
  });
}

function accessToken(request: NextRequest): string | null {
  const authorization = request.headers.get("authorization");
  if (!authorization) return null;
  const [scheme, token, ...extra] = authorization.split(" ");
  return scheme.toLowerCase() === "bearer" && token && extra.length === 0
    ? token
    : null;
}

function scadaBaseUrl(): string {
  const configured =
    process.env.SCADA_GATE_CONTROL_URL ?? "http://localhost:3030";
  const url = new URL(configured);
  if (
    !["http:", "https:"].includes(url.protocol) ||
    url.pathname !== "/" ||
    url.search ||
    url.hash ||
    url.username ||
    url.password
  ) {
    throw new Error("SCADA_GATE_CONTROL_URL must be host-only");
  }
  return url.origin;
}

export async function GET(
  request: NextRequest,
  context: RouteContext,
): Promise<NextResponse> {
  const token = accessToken(request);
  if (!token) return noStore({ error: "Bearer token is required" }, 401);

  const { id } = await context.params;
  if (!id) return noStore({ error: "Gate ID is required" }, 400);

  try {
    const response = await fetch(
      `${scadaBaseUrl()}/api/gates/${encodeURIComponent(id)}/status`,
      {
        method: "GET",
        cache: "no-store",
        redirect: "error",
        headers: { authorization: `Bearer ${token}` },
        signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
      },
    );
    return new NextResponse(await response.text(), {
      status: response.status,
      headers: {
        "Cache-Control": "no-store",
        "Content-Type":
          response.headers.get("content-type") ?? "application/json",
      },
    });
  } catch {
    return noStore({ error: "Gate status service is unavailable" }, 503);
  }
}
