/**
 * PR 6.1b — pure generator + validator for the approved field device & quantizer artifact,
 * plus the dark-by-default lineage-anchor loader.
 *
 * D6 (the per-gate actuator master) is unavailable, so this ships SOFTWARE + a loudly
 * labeled non-field-approved example only. Nothing here actuates, dispatches, or touches
 * Modbus; the rich artifact is never loaded into the runtime process. An operator runs
 * `buildDeviceRegistryArtifact` OFFLINE to produce the endpoint-free device registry that
 * 6.1a's loader consumes, and `extractApprovedLineageAnchor` to produce the small anchor
 * JSON that `loadApprovedLineageAnchor` reads (dark unless `SCADA_APPROVED_LINEAGE_ANCHOR_PATH`
 * is set).
 */
import type { ValidateFunction } from 'ajv/dist/2020';

import {
  APPROVED_FIELD_ARTIFACT_SCHEMA_V1,
  APPROVED_LINEAGE_ANCHOR_SCHEMA_V1,
} from './approved-field-artifact.schema';
import { readCappedJsonFile } from './capped-json-file';
import { ENDPOINT_OR_CREDENTIAL, RESERVED_GATE_KEYS } from './device-registry';
import { newMachineBoundaryAjv } from './machine-boundary-ajv';
import type { CommandLineage } from './machine-boundary';

// ---- Types -----------------------------------------------------------------

export type ApprovedLineageAnchor = {
  readonly model_release_id: string;
  readonly model_release_content_hash: string;
  readonly engine_descriptor_content_hash: string;
};

export type ApprovedFieldTarget = {
  readonly target_position_m: number;
  readonly target_level: number;
};

export type ApprovedFieldGate = {
  readonly canonical_gate_id: string;
  readonly device_id: string;
  readonly adapter_gate_id: string;
  readonly register: {
    readonly unit_id: number;
    readonly command_register: number;
    readonly readback_register: number;
  };
  readonly readback: { readonly tolerance_m: number; readonly settle_ms: number };
  readonly quantizer: { readonly targets: readonly ApprovedFieldTarget[] };
  readonly evidence: ReadonlyArray<{
    readonly kind: string;
    readonly reference: string;
    readonly sha256: string;
  }>;
};

export type ApprovedFieldArtifact = {
  readonly artifact_version: 1;
  readonly capability_release_id: string;
  readonly approval: {
    readonly scope: 'pilot' | 'all-gate';
    readonly approved_by_role: string;
    readonly approved_at: string;
    readonly approval_reference: string;
    readonly evidence: ReadonlyArray<{
      readonly kind: string;
      readonly reference: string;
      readonly sha256: string;
    }>;
  };
  readonly approved_lineage_anchor: ApprovedLineageAnchor;
  readonly gates: readonly ApprovedFieldGate[];
};

/** The endpoint-free device-registry document that 6.1a's `loadDeviceCapabilitySnapshot`
 * consumes: EXACTLY `{ capability_release_id, capabilities }`, each capability EXACTLY
 * `{ device_id, adapter_gate_id, targets }`. */
export type DeviceRegistryDocument = {
  readonly capability_release_id: string;
  readonly capabilities: Readonly<
    Record<
      string,
      {
        readonly device_id: string;
        readonly adapter_gate_id: string;
        readonly targets: readonly ApprovedFieldTarget[];
      }
    >
  >;
};

export class ApprovedFieldArtifactError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ApprovedFieldArtifactError';
  }
}

/** An anchor is a 3-field object; cap the raw file well below the registry cap. */
const MAX_ANCHOR_BYTES = 65_536; // 64 KiB

let cachedArtifactValidator: ValidateFunction | null = null;
function artifactValidator(): ValidateFunction {
  if (cachedArtifactValidator) return cachedArtifactValidator;
  cachedArtifactValidator = newMachineBoundaryAjv().compile(
    APPROVED_FIELD_ARTIFACT_SCHEMA_V1 as unknown as Record<string, unknown>,
  );
  return cachedArtifactValidator;
}

let cachedAnchorValidator: ValidateFunction | null = null;
function anchorValidator(): ValidateFunction {
  if (cachedAnchorValidator) return cachedAnchorValidator;
  cachedAnchorValidator = newMachineBoundaryAjv().compile(
    APPROVED_LINEAGE_ANCHOR_SCHEMA_V1 as unknown as Record<string, unknown>,
  );
  return cachedAnchorValidator;
}

function assertNoEndpoint(field: string, value: string): void {
  if (ENDPOINT_OR_CREDENTIAL.test(value)) {
    throw new ApprovedFieldArtifactError(
      `approved field artifact ${field} must not embed a transport endpoint or credential`,
    );
  }
}

/**
 * Defense-in-depth beyond the shape schema (which permits any printable-ASCII id): reject
 * a `__proto__`/`constructor`/`prototype` canonical_gate_id (it would pollute the PROJECTED
 * capabilities map) and any id VALUE that smuggles a `://` or `@` endpoint/credential. Runs
 * on a schema-valid artifact, before projection. Evidence `reference` values (which may be
 * `doc://` pointers) are deliberately NOT scanned — they never reach the runtime snapshot.
 */
function assertArtifactHygiene(artifact: ApprovedFieldArtifact): void {
  assertNoEndpoint('capability_release_id', artifact.capability_release_id);
  for (const gate of artifact.gates) {
    if (RESERVED_GATE_KEYS.has(gate.canonical_gate_id)) {
      throw new ApprovedFieldArtifactError(
        `canonical_gate_id '${gate.canonical_gate_id}' is a reserved property name`,
      );
    }
    assertNoEndpoint(`canonical_gate_id '${gate.canonical_gate_id}'`, gate.canonical_gate_id);
    assertNoEndpoint(`device_id for gate '${gate.canonical_gate_id}'`, gate.device_id);
    assertNoEndpoint(`adapter_gate_id for gate '${gate.canonical_gate_id}'`, gate.adapter_gate_id);
  }
}

/**
 * Parse untrusted JSON into a typed ApprovedFieldArtifact: Ajv-validate against the embedded
 * v1 schema, then run hygiene. The ONLY entry that accepts untrusted input; the pure
 * generator/validator below assume a parsed artifact.
 */
export function parseApprovedFieldArtifact(raw: unknown): ApprovedFieldArtifact {
  if (!artifactValidator()(raw)) {
    throw new ApprovedFieldArtifactError(
      'approved field artifact does not satisfy the approved-field-artifact v1 contract',
    );
  }
  const artifact = raw as ApprovedFieldArtifact;
  assertArtifactHygiene(artifact);
  return artifact;
}

/** Sort targets by target_level ascending → one canonical order so the projection (and the
 * downstream 6.1a capability_hash) is byte-exact regardless of the artifact's target order.
 * (For a coverage-valid, strictly-monotone quantizer, level order == position order; the two
 * sort keys agree. `validateApprovedRegistryCoverage` is what enforces that co-monotonicity.) */
function sortedTargets(targets: readonly ApprovedFieldTarget[]): ApprovedFieldTarget[] {
  return [...targets]
    .map((t) => ({ target_position_m: t.target_position_m, target_level: t.target_level }))
    .sort((a, b) => a.target_level - b.target_level);
}

/** Total-order string comparator (returns 0 on equal keys, unlike a `< ? -1 : 1` shortcut). */
function compareGateId(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0;
}

/** Reject a duplicate canonical_gate_id. Shared by the projection and the coverage validator so
 * neither can silently keep only the last of two gates that map to the same key. */
function assertUniqueGateIds(gates: readonly ApprovedFieldGate[]): void {
  const seen = new Set<string>();
  for (const gate of gates) {
    if (seen.has(gate.canonical_gate_id)) {
      throw new ApprovedFieldArtifactError(
        `duplicate canonical_gate_id '${gate.canonical_gate_id}' in the approved artifact`,
      );
    }
    seen.add(gate.canonical_gate_id);
  }
}

/**
 * Project the rich artifact down to EXACTLY the endpoint-free `{ capability_release_id,
 * capabilities }` document 6.1a's loader consumes — dropping register/readback/evidence/
 * approval/lineage. Gates are emitted in canonical (gate-id sorted) order and built via
 * `Object.fromEntries` (an OWN-property write, so a hostile gate id cannot pollute the
 * prototype). Deterministic and hash-idempotent.
 *
 * SELF-SAFE: re-runs hygiene (endpoint/credential + reserved gate ids) and the duplicate-gate
 * guard rather than trusting the caller ran `parseApprovedFieldArtifact`/coverage first — a
 * projection in a control plane must never silently drop or leak an approved device.
 */
export function buildDeviceRegistryArtifact(
  approved: ApprovedFieldArtifact,
): DeviceRegistryDocument {
  assertArtifactHygiene(approved);
  assertUniqueGateIds(approved.gates);
  const entries = [...approved.gates]
    .sort((a, b) => compareGateId(a.canonical_gate_id, b.canonical_gate_id))
    .map(
      (gate) =>
        [
          gate.canonical_gate_id,
          {
            device_id: gate.device_id,
            adapter_gate_id: gate.adapter_gate_id,
            targets: sortedTargets(gate.quantizer.targets),
          },
        ] as const,
    );
  return {
    capability_release_id: approved.capability_release_id,
    capabilities: Object.fromEntries(entries),
  };
}

/**
 * Assert every quantizer is a strictly-monotone bijection: sorted by position, each
 * successive position AND level strictly increases. Rejects two positions sharing a level,
 * a level shared across positions, and any position/level inversion — so continuous→discrete
 * quantization stays invertible.
 */
function assertQuantizerMonotone(gateId: string, targets: readonly ApprovedFieldTarget[]): void {
  const byPosition = [...targets].sort((a, b) => a.target_position_m - b.target_position_m);
  let prev: ApprovedFieldTarget | undefined;
  for (const cur of byPosition) {
    if (
      prev &&
      (!(cur.target_position_m > prev.target_position_m) || !(cur.target_level > prev.target_level))
    ) {
      throw new ApprovedFieldArtifactError(
        `quantizer for gate '${gateId}' is not strictly monotone (position and level must both increase)`,
      );
    }
    prev = cur;
  }
}

/**
 * Assert adjacent quantizer positions are separated by MORE than twice the readback
 * tolerance, so an observed readback within tolerance of a commanded position reconciles to
 * exactly one level (the readback round-trip). Without this, two nearby targets make a
 * readback ambiguous and 6.3's reconciler could attribute the wrong level.
 */
function assertReadbackSeparable(
  gateId: string,
  targets: readonly ApprovedFieldTarget[],
  toleranceM: number,
): void {
  const byPosition = [...targets].sort((a, b) => a.target_position_m - b.target_position_m);
  let prev: ApprovedFieldTarget | undefined;
  for (const cur of byPosition) {
    if (prev) {
      const gap = cur.target_position_m - prev.target_position_m;
      if (!(gap > 2 * toleranceM)) {
        throw new ApprovedFieldArtifactError(
          `quantizer for gate '${gateId}' has targets closer than the readback separation ` +
            `(gap ${gap} m <= 2x tolerance ${2 * toleranceM} m)`,
        );
      }
    }
    prev = cur;
  }
}

/**
 * Fail-closed coverage validator for an approved artifact against the EXACT expected
 * approved-gate scope (supplied by the operator/test — never a committed constant, since D6
 * is unavailable). Throws unless the gate set matches exactly (no extra/missing, no
 * duplicates) and every quantizer is monotone/bijective and readback-round-trips.
 */
export function validateApprovedRegistryCoverage(
  approved: ApprovedFieldArtifact,
  expectedApprovedGateIds: ReadonlySet<string>,
): void {
  assertUniqueGateIds(approved.gates);
  const seen = new Set(approved.gates.map((g) => g.canonical_gate_id));
  const missing = [...expectedApprovedGateIds].filter((id) => !seen.has(id));
  if (missing.length > 0) {
    throw new ApprovedFieldArtifactError(
      `approved scope is missing gate(s): ${missing.sort().join(', ')}`,
    );
  }
  const extra = [...seen].filter((id) => !expectedApprovedGateIds.has(id));
  if (extra.length > 0) {
    throw new ApprovedFieldArtifactError(
      `gate(s) not in the approved scope: ${extra.sort().join(', ')}`,
    );
  }
  for (const gate of approved.gates) {
    assertQuantizerMonotone(gate.canonical_gate_id, gate.quantizer.targets);
    assertReadbackSeparable(
      gate.canonical_gate_id,
      gate.quantizer.targets,
      gate.readback.tolerance_m,
    );
  }
}

/** Project the artifact's approved lineage anchor (the 3 pinned fields). Keeps the artifact
 * the single source of the anchor so the offline-produced anchor JSON cannot silently drift. */
export function extractApprovedLineageAnchor(
  approved: ApprovedFieldArtifact,
): ApprovedLineageAnchor {
  const a = approved.approved_lineage_anchor;
  return {
    model_release_id: a.model_release_id,
    model_release_content_hash: a.model_release_content_hash,
    engine_descriptor_content_hash: a.engine_descriptor_content_hash,
  };
}

/**
 * Dark-by-default runtime loader for the lineage anchor.
 *   - Env var UNSET (undefined) → `null` (the `lineage_mismatch` check is a no-op, identical
 *     to 6.2). This is the intended "not configured" dark default.
 *   - Env var SET but blank/whitespace → THROW. Unlike 6.1a's registry (whose blank default is
 *     the SAFE zero-gates snapshot), an empty anchor path would silently DISABLE a safety check
 *     — the opposite safety valence — so a configured-to-blank path must fail loud, never run
 *     dark. (To disable the check, UNSET the var, don't blank it.)
 *   - Set-but-unreadable/oversized/malformed/contract-violating → THROW at startup: opting in is
 *     deliberate, so a broken anchor fails loud and never silently disables the check.
 *
 * NOTE (idempotency interaction, documented — see services/scada-gate-control/CLAUDE.md): a 6.2
 * ValidationReceipt is frozen at first validation under the then-current anchor policy, so a
 * receipt minted while dark REPLAYS verbatim after arming. Arming the anchor is a trust-policy
 * change that must be paired with rotating the `scada_command_intents` receipt store (or done at
 * the external trust cutover on a fresh store) so no pre-arm receipt masks the armed check.
 */
export function loadApprovedLineageAnchor(
  env: NodeJS.ProcessEnv = process.env,
): ApprovedLineageAnchor | null {
  const rawPath = env.SCADA_APPROVED_LINEAGE_ANCHOR_PATH;
  if (rawPath === undefined) return null; // truly unconfigured → dark (6.2-identical)
  const path = rawPath.trim();
  if (path === '') {
    throw new ApprovedFieldArtifactError(
      'SCADA_APPROVED_LINEAGE_ANCHOR_PATH is set but blank — refusing to run the lineage check ' +
        'dark; UNSET the variable to disable the check deliberately',
    );
  }

  const parsed = readCappedJsonFile(
    path,
    MAX_ANCHOR_BYTES,
    {
      unreadable: 'SCADA_APPROVED_LINEAGE_ANCHOR_PATH is set but the anchor file cannot be read',
      tooBig: 'approved lineage anchor file exceeds the 64 KiB size cap',
      notJson: 'approved lineage anchor is not valid JSON',
    },
    (m) => new ApprovedFieldArtifactError(m),
  );
  if (!anchorValidator()(parsed)) {
    throw new ApprovedFieldArtifactError(
      'approved lineage anchor does not satisfy the approved-lineage-anchor v1 contract',
    );
  }
  const a = parsed as ApprovedLineageAnchor;
  return {
    model_release_id: a.model_release_id,
    model_release_content_hash: a.model_release_content_hash,
    engine_descriptor_content_hash: a.engine_descriptor_content_hash,
  };
}

/** Exact equality on the 3 pinned "approved commandable release" fields. Used ONLY inside
 * `validateCommandIntent` (position 4) when an anchor is configured. */
export function lineageMatchesAnchor(
  lineage: CommandLineage,
  anchor: ApprovedLineageAnchor,
): boolean {
  return (
    lineage.model_release_id === anchor.model_release_id &&
    lineage.model_release_content_hash === anchor.model_release_content_hash &&
    lineage.engine_descriptor_content_hash === anchor.engine_descriptor_content_hash
  );
}
