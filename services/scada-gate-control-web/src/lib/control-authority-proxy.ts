const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const SHA256 = /^[0-9a-f]{64}$/;
const UPSTREAM_TIMEOUT_MS = 5_000;

export type AuthorityBlocker =
  | "plan_not_shadow_active"
  | "noncommandable_release"
  | "capability_unconfigured"
  | "capability_stale"
  | "scope_unapproved_gate"
  | "receipt_coverage_incomplete"
  | "plan_envelope_empty"
  | "grant_already_exists";

export type AuthorityApplicability = {
  plan_id: string;
  plan_version: number;
  evaluated_at: string;
  lifecycle_state: string;
  model_release_id: string;
  model_release_content_hash: string;
  engine_descriptor_content_hash: string;
  model_release_commandable: boolean;
  capability_release_id: string;
  capability_hash: string;
  capability_configured: boolean;
  capability_matches_outbox: boolean;
  scope: {
    schema_version: 1;
    gate_paths: Array<{
      section_id: string;
      canonical_gate_id: string;
      path_reach_ids: string[];
    }>;
  };
  flow_lower_exclusive_m3s: number;
  flow_upper_inclusive_m3s: number;
  initialization: { kind: "dry" };
  maximum_continuous_open_seconds: number;
  maximum_intermediate_trims: number;
  outbox_intent_count: number;
  accepted_receipt_intent_count: number;
  matching_receipt_intent_count: number;
  receipt_coverage_complete: boolean;
  existing_grant_status: "active" | "expired" | "revoked" | null;
  existing_grant_id: string | null;
  blockers: AuthorityBlocker[];
  can_grant: boolean;
};

export type AuthorityGrant = {
  grant_id: string;
  plan_id: string;
  plan_version: number;
  status: "active" | "expired" | "revoked";
  effective_expires_at: string;
  model_release_id: string;
  model_release_content_hash: string;
  engine_descriptor_content_hash: string;
  capability_release_id: string;
  capability_hash: string;
  grant_content_sha256: string;
  events: Array<{
    event_sequence: number;
    event_type: "granted" | "renewed" | "revoked";
    effective_expires_at: string | null;
    actor_subject: string;
    reason: string;
    occurred_at: string;
  }>;
};

export type ScadaAuthorityStatus = {
  available: boolean;
  healthy: boolean;
  capability_release_id: string | null;
  capability_hash: string | null;
  matches_scheduler: boolean;
};

export type ControlAuthorityDashboard = {
  applicability: AuthorityApplicability;
  grant: AuthorityGrant | null;
  scada: ScadaAuthorityStatus;
};

export type ControlAuthorityProxyDeps = {
  schedulerBaseUrl: string;
  scadaBaseUrl: string;
  fetchImpl?: typeof fetch;
};

type ReadInput = {
  planId: string;
  planVersion: number;
  accessToken: string;
};

export type MutationAction =
  | "approve-shadow"
  | "activate"
  | "hold"
  | "resume"
  | "grant"
  | "renew"
  | "revoke";

export type MutationInput = ReadInput & {
  action: MutationAction;
  confirmation: string;
  stepUpCode?: string;
  reason: string;
  grantId?: string;
  approvalRefs?: string[];
  evidenceRefs?: string[];
  shadowEvidenceSha256?: string;
  holdDrillEvidenceSha256?: string;
  rollbackDrillEvidenceSha256?: string;
  expiresAt?: string;
};

export class ControlAuthorityProxyError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ControlAuthorityProxyError";
  }
}

function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new ControlAuthorityProxyError("Upstream contract violation", 502);
  }
  return value as Record<string, unknown>;
}

function hostOnlyBaseUrl(value: string, name: string): string {
  const url = new URL(value);
  if (
    !["http:", "https:"].includes(url.protocol) ||
    url.pathname !== "/" ||
    url.search ||
    url.hash ||
    url.username ||
    url.password
  ) {
    throw new ControlAuthorityProxyError(`${name} URL must be host-only`, 503);
  }
  return url.origin;
}

function requireReadInput(input: ReadInput): void {
  if (
    !UUID.test(input.planId) ||
    !Number.isInteger(input.planVersion) ||
    input.planVersion <= 0 ||
    !input.accessToken
  ) {
    throw new ControlAuthorityProxyError("Invalid authority request", 400);
  }
}

async function responseJson(response: Response): Promise<unknown> {
  try {
    return JSON.parse(await response.text()) as unknown;
  } catch {
    throw new ControlAuthorityProxyError("Upstream returned invalid JSON", 502);
  }
}

async function send(
  fetchImpl: typeof fetch,
  url: string,
  accessToken: string | undefined,
  init: RequestInit = {},
): Promise<Response> {
  try {
    return await fetchImpl(url, {
      ...init,
      cache: "no-store",
      signal: init.signal ?? AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
      headers: {
        ...(accessToken ? { authorization: `Bearer ${accessToken}` } : {}),
        ...(init.headers ?? {}),
      },
    });
  } catch {
    throw new ControlAuthorityProxyError("Upstream is unavailable", 503);
  }
}

function assertStatus(response: Response): void {
  if (response.ok) return;
  if ([401, 403, 404, 409, 422].includes(response.status)) {
    throw new ControlAuthorityProxyError("Upstream rejected the request", response.status);
  }
  throw new ControlAuthorityProxyError("Upstream is unavailable", 503);
}

const BLOCKERS = new Set<AuthorityBlocker>([
  "plan_not_shadow_active",
  "noncommandable_release",
  "capability_unconfigured",
  "capability_stale",
  "scope_unapproved_gate",
  "receipt_coverage_incomplete",
  "plan_envelope_empty",
  "grant_already_exists",
]);

function parseApplicability(value: unknown): AuthorityApplicability {
  const body = record(value);
  const scope = record(body.scope);
  const initialization = record(body.initialization);
  const gatePaths = scope.gate_paths;
  const blockers = body.blockers;
  const valid =
    typeof body.plan_id === "string" &&
    UUID.test(body.plan_id) &&
    Number.isInteger(body.plan_version) &&
    typeof body.evaluated_at === "string" &&
    typeof body.lifecycle_state === "string" &&
    typeof body.model_release_id === "string" &&
    typeof body.model_release_content_hash === "string" &&
    SHA256.test(body.model_release_content_hash) &&
    typeof body.engine_descriptor_content_hash === "string" &&
    SHA256.test(body.engine_descriptor_content_hash) &&
    typeof body.model_release_commandable === "boolean" &&
    typeof body.capability_release_id === "string" &&
    typeof body.capability_hash === "string" &&
    SHA256.test(body.capability_hash) &&
    typeof body.capability_configured === "boolean" &&
    typeof body.capability_matches_outbox === "boolean" &&
    scope.schema_version === 1 &&
    Array.isArray(gatePaths) &&
    gatePaths.every((entry) => {
      const path = record(entry);
      return (
        typeof path.section_id === "string" &&
        typeof path.canonical_gate_id === "string" &&
        Array.isArray(path.path_reach_ids) &&
        path.path_reach_ids.every((reach) => typeof reach === "string")
      );
    }) &&
    typeof body.flow_lower_exclusive_m3s === "number" &&
    typeof body.flow_upper_inclusive_m3s === "number" &&
    initialization.kind === "dry" &&
    Number.isInteger(body.maximum_continuous_open_seconds) &&
    Number.isInteger(body.maximum_intermediate_trims) &&
    Number.isInteger(body.outbox_intent_count) &&
    Number.isInteger(body.accepted_receipt_intent_count) &&
    Number.isInteger(body.matching_receipt_intent_count) &&
    typeof body.receipt_coverage_complete === "boolean" &&
    (body.existing_grant_status === null ||
      ["active", "expired", "revoked"].includes(String(body.existing_grant_status))) &&
    (body.existing_grant_id === null ||
      (typeof body.existing_grant_id === "string" && UUID.test(body.existing_grant_id))) &&
    Array.isArray(blockers) &&
    blockers.every((blocker) => BLOCKERS.has(blocker as AuthorityBlocker)) &&
    typeof body.can_grant === "boolean";
  if (!valid) throw new ControlAuthorityProxyError("Applicability contract violation", 502);
  return body as AuthorityApplicability;
}

function parseGrant(value: unknown): AuthorityGrant {
  const body = record(value);
  const events = body.events;
  const validEvents =
    Array.isArray(events) &&
    events.length > 0 &&
    events.every((entry, index) => {
      const event = record(entry);
      return (
        event.event_sequence === index + 1 &&
        ["granted", "renewed", "revoked"].includes(String(event.event_type)) &&
        (typeof event.effective_expires_at === "string" ||
          event.effective_expires_at === null) &&
        typeof event.actor_subject === "string" &&
        event.actor_subject.length > 0 &&
        typeof event.reason === "string" &&
        event.reason.length > 0 &&
        typeof event.occurred_at === "string"
      );
    });
  const eventRecords = validEvents
    ? (events as Array<Record<string, unknown>>)
    : [];
  const terminalIndex = eventRecords.findIndex(
    (event) => event.event_type === "revoked",
  );
  const lastAuthorityEvent = [...eventRecords]
    .reverse()
    .find((event) => event.event_type !== "revoked");
  const valid =
    typeof body.grant_id === "string" &&
    UUID.test(body.grant_id) &&
    typeof body.plan_id === "string" &&
    UUID.test(body.plan_id) &&
    Number.isInteger(body.plan_version) &&
    ["active", "expired", "revoked"].includes(String(body.status)) &&
    typeof body.effective_expires_at === "string" &&
    typeof body.model_release_id === "string" &&
    typeof body.model_release_content_hash === "string" &&
    SHA256.test(body.model_release_content_hash) &&
    typeof body.engine_descriptor_content_hash === "string" &&
    SHA256.test(body.engine_descriptor_content_hash) &&
    typeof body.capability_release_id === "string" &&
    typeof body.capability_hash === "string" &&
    SHA256.test(body.capability_hash) &&
    typeof body.grant_content_sha256 === "string" &&
    SHA256.test(body.grant_content_sha256) &&
    validEvents &&
    eventRecords[0]?.event_type === "granted" &&
    eventRecords.slice(1).every((event) => event.event_type !== "granted") &&
    (terminalIndex === -1 || terminalIndex === eventRecords.length - 1) &&
    (body.status === "revoked") === (terminalIndex !== -1) &&
    lastAuthorityEvent?.effective_expires_at === body.effective_expires_at;
  if (!valid) throw new ControlAuthorityProxyError("Grant contract violation", 502);
  return body as AuthorityGrant;
}

function query(planId: string, planVersion: number): string {
  return new URLSearchParams({
    plan_id: planId,
    plan_version: String(planVersion),
  }).toString();
}

async function readScheduler(
  input: ReadInput,
  scheduler: string,
  fetchImpl: typeof fetch,
): Promise<{ applicability: AuthorityApplicability; grant: AuthorityGrant | null }> {
  const suffix = query(input.planId, input.planVersion);
  const [applicabilityResponse, grantResponse] = await Promise.all([
    send(
      fetchImpl,
      `${scheduler}/api/v1/authority-grants/applicability?${suffix}`,
      input.accessToken,
    ),
    send(
      fetchImpl,
      `${scheduler}/api/v1/authority-grants?${suffix}`,
      input.accessToken,
    ),
  ]);
  assertStatus(applicabilityResponse);
  const applicability = parseApplicability(await responseJson(applicabilityResponse));
  if (
    applicability.plan_id !== input.planId ||
    applicability.plan_version !== input.planVersion
  ) {
    throw new ControlAuthorityProxyError("Applicability identity violation", 502);
  }
  if (grantResponse.status === 404) {
    if (
      applicability.existing_grant_id !== null ||
      applicability.existing_grant_status !== null
    ) {
      throw new ControlAuthorityProxyError("Authority state contract violation", 502);
    }
    return { applicability, grant: null };
  }
  assertStatus(grantResponse);
  const grant = parseGrant(await responseJson(grantResponse));
  if (
    grant.plan_id !== input.planId ||
    grant.plan_version !== input.planVersion ||
    applicability.existing_grant_id !== grant.grant_id ||
    grant.model_release_id !== applicability.model_release_id ||
    grant.model_release_content_hash !== applicability.model_release_content_hash ||
    grant.engine_descriptor_content_hash !==
      applicability.engine_descriptor_content_hash ||
    grant.capability_release_id !== applicability.capability_release_id ||
    grant.capability_hash !== applicability.capability_hash
  ) {
    throw new ControlAuthorityProxyError("Authority state contract violation", 502);
  }
  return { applicability, grant };
}

async function readGrantById(
  grantId: string,
  accessToken: string,
  scheduler: string,
  fetchImpl: typeof fetch,
): Promise<AuthorityGrant> {
  const response = await send(
    fetchImpl,
    `${scheduler}/api/v1/authority-grants/${encodeURIComponent(grantId)}`,
    accessToken,
  );
  assertStatus(response);
  return parseGrant(await responseJson(response));
}

async function readScada(
  input: ReadInput,
  scadaBaseUrl: string,
  fetchImpl: typeof fetch,
  applicability: AuthorityApplicability,
): Promise<ScadaAuthorityStatus> {
  try {
    const scada = hostOnlyBaseUrl(scadaBaseUrl, "SCADA");
    const [healthResponse, capabilityResponse] = await Promise.all([
      send(fetchImpl, `${scada}/health`, undefined),
      send(
        fetchImpl,
        `${scada}/internal/v1/device-capabilities`,
        input.accessToken,
      ),
    ]);
    if (healthResponse.status >= 500 || capabilityResponse.status >= 500) {
      throw new ControlAuthorityProxyError("SCADA unavailable", 503);
    }
    assertStatus(healthResponse);
    assertStatus(capabilityResponse);
    const health = record(await responseJson(healthResponse));
    const capability = record(await responseJson(capabilityResponse));
    if (
      health.status !== "healthy" ||
      health.service !== "scada-gate-control" ||
      typeof capability.capability_release_id !== "string" ||
      typeof capability.capability_hash !== "string" ||
      !SHA256.test(capability.capability_hash)
    ) {
      throw new ControlAuthorityProxyError("SCADA contract violation", 502);
    }
    return {
      available: true,
      healthy: true,
      capability_release_id: capability.capability_release_id,
      capability_hash: capability.capability_hash,
      matches_scheduler:
        capability.capability_release_id === applicability.capability_release_id &&
        capability.capability_hash === applicability.capability_hash,
    };
  } catch {
    return {
      available: false,
      healthy: false,
      capability_release_id: null,
      capability_hash: null,
      matches_scheduler: false,
    };
  }
}

export async function readControlAuthority(
  input: ReadInput,
  deps: ControlAuthorityProxyDeps,
): Promise<ControlAuthorityDashboard> {
  requireReadInput(input);
  const scheduler = hostOnlyBaseUrl(deps.schedulerBaseUrl, "Scheduler");
  const fetchImpl = deps.fetchImpl ?? fetch;
  const schedulerState = await readScheduler(input, scheduler, fetchImpl);
  return {
    ...schedulerState,
    scada: await readScada(
      input,
      deps.scadaBaseUrl,
      fetchImpl,
      schedulerState.applicability,
    ),
  };
}

const ACTIONS = new Set<MutationAction>([
  "approve-shadow",
  "activate",
  "hold",
  "resume",
  "grant",
  "renew",
  "revoke",
]);

function requireStrings(values: Array<unknown>): asserts values is string[] {
  if (values.some((value) => typeof value !== "string" || !value.trim())) {
    throw new ControlAuthorityProxyError("Required authority evidence is missing", 400);
  }
}

async function post(
  fetchImpl: typeof fetch,
  url: string,
  input: MutationInput,
  body: object,
): Promise<unknown> {
  const headers: Record<string, string> = {
    "content-type": "application/json",
    "x-operator-confirmation": input.confirmation,
  };
  if (input.stepUpCode) headers["x-operator-step-up-code"] = input.stepUpCode;
  const response = await send(fetchImpl, url, input.accessToken, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
  assertStatus(response);
  return responseJson(response);
}

export async function mutateControlAuthority(
  input: MutationInput,
  deps: ControlAuthorityProxyDeps,
): Promise<unknown> {
  if (!ACTIONS.has(input.action)) {
    throw new ControlAuthorityProxyError("Unsupported authority action", 400);
  }
  requireReadInput(input);
  requireStrings([input.confirmation, input.reason]);
  const scheduler = hostOnlyBaseUrl(deps.schedulerBaseUrl, "Scheduler");
  const fetchImpl = deps.fetchImpl ?? fetch;
  const planPath = `${scheduler}/api/v1/control-plans/${encodeURIComponent(input.planId)}/versions/${input.planVersion}`;

  if (["approve-shadow", "activate"].includes(input.action)) {
    requireStrings(input.approvalRefs ?? []);
    return post(fetchImpl, `${planPath}/${input.action === "approve-shadow" ? "approve-for-shadow" : "activate"}`, input, {
      reason: input.reason,
      evidence_refs: input.approvalRefs,
    });
  }
  if (["hold", "resume"].includes(input.action)) {
    return post(fetchImpl, `${planPath}/${input.action}`, input, { reason: input.reason });
  }
  if (input.action === "grant") {
    requireStrings([
      input.stepUpCode,
      ...(input.approvalRefs ?? []),
      input.shadowEvidenceSha256,
      input.holdDrillEvidenceSha256,
      input.rollbackDrillEvidenceSha256,
      ...(input.evidenceRefs ?? []),
      input.expiresAt,
    ]);
    const state = await readScheduler(input, scheduler, fetchImpl);
    if (!state.applicability.can_grant) {
      throw new ControlAuthorityProxyError("Plan is not grantable", 409);
    }
    const app = state.applicability;
    return post(fetchImpl, `${scheduler}/api/v1/authority-grants`, input, {
      plan_id: app.plan_id,
      plan_version: app.plan_version,
      model_release_id: app.model_release_id,
      model_release_content_hash: app.model_release_content_hash,
      engine_descriptor_content_hash: app.engine_descriptor_content_hash,
      commandability_evidence: {
        schema_version: 1,
        model_release_id: app.model_release_id,
        model_release_content_hash: app.model_release_content_hash,
        engine_descriptor_content_hash: app.engine_descriptor_content_hash,
        commandable: true,
        approval_refs: input.approvalRefs,
      },
      capability_release_id: app.capability_release_id,
      capability_hash: app.capability_hash,
      scope: app.scope,
      flow_lower_exclusive_m3s: app.flow_lower_exclusive_m3s,
      flow_upper_inclusive_m3s: app.flow_upper_inclusive_m3s,
      initialization: app.initialization,
      maximum_continuous_open_seconds: app.maximum_continuous_open_seconds,
      maximum_intermediate_trims: app.maximum_intermediate_trims,
      shadow_evidence_sha256: input.shadowEvidenceSha256,
      hold_drill_evidence_sha256: input.holdDrillEvidenceSha256,
      rollback_drill_evidence_sha256: input.rollbackDrillEvidenceSha256,
      evidence_manifest: { schema_version: 1, refs: input.evidenceRefs },
      expires_at: input.expiresAt,
      reason: input.reason,
    });
  }
  requireStrings([input.grantId]);
  const grantId = input.grantId as string;
  if (!UUID.test(grantId)) {
    throw new ControlAuthorityProxyError("Invalid grant id", 400);
  }
  if (input.action === "revoke") {
    const grant = await readGrantById(
      grantId,
      input.accessToken,
      scheduler,
      fetchImpl,
    );
    if (grant.plan_id !== input.planId || grant.plan_version !== input.planVersion) {
      throw new ControlAuthorityProxyError("Grant does not belong to the plan", 409);
    }
    return post(fetchImpl, `${scheduler}/api/v1/authority-grants/${grantId}/revocations`, input, {
      reason: input.reason,
    });
  }
  const state = await readScheduler(input, scheduler, fetchImpl);
  if (!state.grant || state.grant.grant_id !== grantId) {
    throw new ControlAuthorityProxyError("Grant does not belong to the plan", 409);
  }
  requireStrings([
    input.stepUpCode,
    input.shadowEvidenceSha256,
    input.holdDrillEvidenceSha256,
    input.rollbackDrillEvidenceSha256,
    ...(input.evidenceRefs ?? []),
    input.expiresAt,
  ]);
  return post(fetchImpl, `${scheduler}/api/v1/authority-grants/${grantId}/renewals`, input, {
    new_expires_at: input.expiresAt,
    shadow_evidence_sha256: input.shadowEvidenceSha256,
    hold_drill_evidence_sha256: input.holdDrillEvidenceSha256,
    rollback_drill_evidence_sha256: input.rollbackDrillEvidenceSha256,
    evidence_manifest: { schema_version: 1, refs: input.evidenceRefs },
    reason: input.reason,
  });
}
