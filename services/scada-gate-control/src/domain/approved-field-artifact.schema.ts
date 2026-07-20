/**
 * PR 6.1b — the "approved field device & quantizer artifact" schemas, EMBEDDED.
 *
 * These are NEW, service-owned schemas — deliberately NOT added under
 * `contracts/machine-boundary/v1/`, because that tree's `manifest.json:contract_set_sha256`
 * is the FROZEN `MACHINE_BOUNDARY_CONTRACT_SET_SHA256` (machine-boundary.ts) mirrored by
 * the scheduler; adding a file there would break every drift-guard. Embedding also means
 * the dist-only PM2 deploy needs no repo-root `contracts/` tree at runtime (same reason as
 * 6.1a's `device-capability-snapshot.schema.ts`).
 *
 * `APPROVED_FIELD_ARTIFACT_SCHEMA_V1` is the RICH, offline artifact: canonical gate +
 * device/adapter + register/unit + discrete quantizer + readback semantics + evidence
 * references + approval metadata + the approved lineage anchor. It is NEVER loaded into
 * the SCADA runtime — an operator runs the pure generator OFFLINE to project it down to
 * the two small env inputs (the endpoint-free device registry that 6.1a's loader reads,
 * and the standalone lineage-anchor JSON below).
 *
 * `APPROVED_LINEAGE_ANCHOR_SCHEMA_V1` is that small standalone anchor, loaded at runtime
 * (dark-by-default) to drive the reserved `lineage_mismatch` reason in 6.2's
 * `validateCommandIntent`. It pins the "approved commandable release" compute identity
 * (model release + engine descriptor) — stable across plan versions — and deliberately
 * excludes per-plan/per-run fields (campaign/plan/prediction/artifact) so a new plan
 * version under the same approved model release is not rejected.
 */

const SHA256 = { type: 'string', minLength: 64, maxLength: 64, pattern: '^[0-9a-f]{64}$' } as const;
const ID_TOKEN = { type: 'string', minLength: 1, maxLength: 128, pattern: '^[!-~]+$' } as const;
const RELEASE_ID = { type: 'string', minLength: 1, maxLength: 256, pattern: '^[!-~]+$' } as const;
const UTC_INSTANT = {
  type: 'string',
  minLength: 20,
  maxLength: 27,
  pattern:
    '^[0-9]{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])T(0[0-9]|1[0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](\\.[0-9]{1,6})?Z$',
} as const;

/** The 3 pinned fields — kept as a named object so the standalone anchor schema and the
 * rich artifact's `approved_lineage_anchor` sub-schema are provably the same shape. */
const APPROVED_LINEAGE_ANCHOR_OBJECT = {
  type: 'object',
  additionalProperties: false,
  required: ['model_release_id', 'model_release_content_hash', 'engine_descriptor_content_hash'],
  properties: {
    model_release_id: RELEASE_ID,
    model_release_content_hash: SHA256,
    engine_descriptor_content_hash: SHA256,
  },
} as const;

export const APPROVED_LINEAGE_ANCHOR_SCHEMA_V1 = {
  $schema: 'https://json-schema.org/draft/2020-12/schema',
  $id: 'https://munbon.internal/scada/approved-lineage-anchor.schema.json',
  title: 'ScadaApprovedLineageAnchorV1',
  description:
    'Dark-by-default runtime anchor for the reserved lineage_mismatch check. Pins ONLY the approved commandable-release compute identity (model release + engine descriptor), stable across plan versions.',
  ...APPROVED_LINEAGE_ANCHOR_OBJECT,
} as const;

export const APPROVED_FIELD_ARTIFACT_SCHEMA_V1 = {
  $schema: 'https://json-schema.org/draft/2020-12/schema',
  $id: 'https://munbon.internal/scada/approved-field-artifact.schema.json',
  title: 'ScadaApprovedFieldArtifactV1',
  description:
    'Offline, content-approvable field device & quantizer artifact (D6/RID-gated). Projected by the pure generator into the endpoint-free device registry (6.1a) + the standalone lineage anchor. Register/readback/evidence/approval NEVER reach the runtime snapshot or its hash. Committed only as a loudly-labeled NON-field-approved example.',
  type: 'object',
  additionalProperties: false,
  required: [
    'artifact_version',
    'capability_release_id',
    'approval',
    'approved_lineage_anchor',
    'gates',
  ],
  properties: {
    artifact_version: { const: 1 },
    capability_release_id: { $ref: '#/$defs/id_token' },
    approval: {
      type: 'object',
      additionalProperties: false,
      required: ['scope', 'approved_by_role', 'approved_at', 'approval_reference', 'evidence'],
      properties: {
        scope: { enum: ['pilot', 'all-gate'] },
        // A ROLE, never a person's name or credential.
        approved_by_role: { type: 'string', minLength: 1, maxLength: 128 },
        approved_at: { $ref: '#/$defs/utc_instant' },
        approval_reference: { type: 'string', minLength: 1, maxLength: 256 },
        evidence: { $ref: '#/$defs/evidence_list' },
      },
    },
    approved_lineage_anchor: APPROVED_LINEAGE_ANCHOR_OBJECT,
    gates: { type: 'array', minItems: 1, items: { $ref: '#/$defs/gate' } },
  },
  $defs: {
    sha256: SHA256,
    id_token: ID_TOKEN,
    release_id: RELEASE_ID,
    utc_instant: UTC_INSTANT,
    position_m: { type: 'number', minimum: 0, maximum: 1000 },
    target_level: { type: 'integer', minimum: 0, maximum: 65535 },
    evidence_ref: {
      type: 'object',
      additionalProperties: false,
      required: ['kind', 'reference', 'sha256'],
      properties: {
        kind: { type: 'string', minLength: 1, maxLength: 64 },
        // A pointer (may be a doc:// URI); endpoint-hygiene does NOT scan evidence.
        reference: { type: 'string', minLength: 1, maxLength: 512 },
        sha256: { $ref: '#/$defs/sha256' },
      },
    },
    evidence_list: { type: 'array', items: { $ref: '#/$defs/evidence_ref' } },
    gate: {
      type: 'object',
      additionalProperties: false,
      required: [
        'canonical_gate_id',
        'device_id',
        'adapter_gate_id',
        'register',
        'readback',
        'quantizer',
        'evidence',
      ],
      properties: {
        canonical_gate_id: { $ref: '#/$defs/id_token' },
        device_id: { $ref: '#/$defs/id_token' },
        adapter_gate_id: { $ref: '#/$defs/id_token' },
        register: {
          type: 'object',
          additionalProperties: false,
          required: ['unit_id', 'command_register', 'readback_register'],
          properties: {
            // Modbus map constants (not secrets); PROJECTED AWAY from the runtime snapshot.
            unit_id: { type: 'integer', minimum: 0, maximum: 255 },
            command_register: { type: 'integer', minimum: 0, maximum: 65535 },
            readback_register: { type: 'integer', minimum: 0, maximum: 65535 },
          },
        },
        readback: {
          type: 'object',
          additionalProperties: false,
          required: ['tolerance_m', 'settle_ms'],
          properties: {
            tolerance_m: { type: 'number', exclusiveMinimum: 0, maximum: 1000 },
            settle_ms: { type: 'integer', minimum: 0, maximum: 3_600_000 },
          },
        },
        quantizer: {
          type: 'object',
          additionalProperties: false,
          required: ['targets'],
          properties: {
            targets: {
              type: 'array',
              minItems: 1,
              uniqueItems: true,
              items: { $ref: '#/$defs/target' },
            },
          },
        },
        evidence: { $ref: '#/$defs/evidence_list' },
      },
    },
    target: {
      type: 'object',
      additionalProperties: false,
      required: ['target_position_m', 'target_level'],
      properties: {
        target_position_m: { $ref: '#/$defs/position_m' },
        target_level: { $ref: '#/$defs/target_level' },
      },
    },
  },
} as const;
