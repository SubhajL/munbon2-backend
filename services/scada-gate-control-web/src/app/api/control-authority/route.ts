import { NextResponse, type NextRequest } from "next/server";
import {
  ControlAuthorityProxyError,
  mutateControlAuthority,
  readControlAuthority,
  type MutationInput,
} from "@/lib/control-authority-proxy";

const SCHEDULER_URL = process.env.SCHEDULER_URL ?? "http://localhost:3021";
const SCADA_URL =
  process.env.SCADA_GATE_CONTROL_URL ?? "http://localhost:3030";
const ACTIONS = new Set<MutationInput["action"]>([
  "approve-shadow",
  "activate",
  "hold",
  "resume",
  "grant",
  "renew",
  "revoke",
]);
const BODY_FIELDS = new Set([
  "action",
  "planId",
  "planVersion",
  "reason",
  "grantId",
  "approvalRefs",
  "evidenceRefs",
  "shadowEvidenceSha256",
  "holdDrillEvidenceSha256",
  "rollbackDrillEvidenceSha256",
  "expiresAt",
]);

function noStore(body: unknown, status = 200): NextResponse {
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

function proxyError(error: unknown): NextResponse {
  if (error instanceof ControlAuthorityProxyError) {
    return noStore({ error: error.message }, error.status);
  }
  return noStore({ error: "Control authority service is unavailable" }, 503);
}

export async function GET(request: NextRequest): Promise<NextResponse> {
  const token = accessToken(request);
  if (!token) return noStore({ error: "Bearer token is required" }, 401);
  const planId = request.nextUrl.searchParams.get("planId") ?? "";
  const planVersion = Number(request.nextUrl.searchParams.get("planVersion"));
  try {
    return noStore(
      await readControlAuthority(
        { planId, planVersion, accessToken: token },
        {
          schedulerBaseUrl: SCHEDULER_URL,
          scadaBaseUrl: SCADA_URL,
        },
      ),
    );
  } catch (error) {
    return proxyError(error);
  }
}

function stringArray(value: unknown): string[] | undefined {
  return Array.isArray(value) && value.every((item) => typeof item === "string")
    ? value
    : undefined;
}

export async function POST(request: NextRequest): Promise<NextResponse> {
  const token = accessToken(request);
  if (!token) return noStore({ error: "Bearer token is required" }, 401);
  const parsed = (await request.json().catch(() => null)) as unknown;
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    return noStore({ error: "A JSON object is required" }, 400);
  }
  const body = parsed as Record<string, unknown>;
  if (Object.keys(body).some((key) => !BODY_FIELDS.has(key))) {
    return noStore({ error: "Unexpected authority request field" }, 400);
  }
  if (
    typeof body.action !== "string" ||
    !ACTIONS.has(body.action as MutationInput["action"]) ||
    typeof body.planId !== "string" ||
    typeof body.planVersion !== "number" ||
    typeof body.reason !== "string"
  ) {
    return noStore({ error: "Invalid authority action" }, 400);
  }
  const input: MutationInput = {
    action: body.action as MutationInput["action"],
    planId: body.planId,
    planVersion: body.planVersion,
    accessToken: token,
    confirmation: request.headers.get("x-operator-confirmation") ?? "",
    stepUpCode:
      request.headers.get("x-operator-step-up-code") ?? undefined,
    reason: body.reason,
    grantId: typeof body.grantId === "string" ? body.grantId : undefined,
    approvalRefs: stringArray(body.approvalRefs),
    evidenceRefs: stringArray(body.evidenceRefs),
    shadowEvidenceSha256:
      typeof body.shadowEvidenceSha256 === "string"
        ? body.shadowEvidenceSha256
        : undefined,
    holdDrillEvidenceSha256:
      typeof body.holdDrillEvidenceSha256 === "string"
        ? body.holdDrillEvidenceSha256
        : undefined,
    rollbackDrillEvidenceSha256:
      typeof body.rollbackDrillEvidenceSha256 === "string"
        ? body.rollbackDrillEvidenceSha256
        : undefined,
    expiresAt:
      typeof body.expiresAt === "string" ? body.expiresAt : undefined,
  };
  try {
    return noStore(
      await mutateControlAuthority(input, {
        schedulerBaseUrl: SCHEDULER_URL,
        scadaBaseUrl: SCADA_URL,
      }),
    );
  } catch (error) {
    return proxyError(error);
  }
}
