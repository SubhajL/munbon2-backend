/**
 * PR 6.2a — the command-intent v1 JSON Schema, EMBEDDED in the service.
 *
 * The single source of truth remains
 * `contracts/machine-boundary/v1/command-intent.schema.json` (PR 6.0);
 * `command-intent.schema.spec.ts` is a drift-guard that asserts this const is
 * structurally identical to that file. We embed it for the same reason as
 * `device-capability-snapshot.schema.ts` (6.1a): the PM2/dist deploy ships only
 * `services/scada-gate-control/dist`, so the repo-root `contracts/` tree is NOT
 * present at runtime and reading the schema off disk would fail closed. Ajv 2020
 * compiles this const to validate an incoming CommandIntent at the machine boundary.
 */
export const COMMAND_INTENT_SCHEMA_V1 = {
  $schema: 'https://json-schema.org/draft/2020-12/schema',
  $id: 'https://munbon.internal/contracts/machine-boundary/v1/command-intent.schema.json',
  title: 'MachineBoundaryCommandIntentV1',
  description:
    'Scheduler -> SCADA shadow command intent. Structural contract only; capability freshness, deadline ordering, quantizer membership, and lineage lookup are runtime semantics owned by 4.3c/6.1a/6.2. All identifiers are printable ASCII (no language-dependent Unicode-whitespace classes) so Python jsonschema/pydantic and TypeScript Ajv agree on every input.',
  type: 'object',
  additionalProperties: false,
  required: [
    'schema_version',
    'intent_id',
    'correlation_id',
    'request_id',
    'idempotency_key',
    'canonical_gate_id',
    'event_kind',
    'event_sequence',
    'gate_event_sequence',
    'device_id',
    'adapter_gate_id',
    'capability_release_id',
    'capability_hash',
    'target_position_m',
    'target_level',
    'not_before',
    'deadline',
    'mode',
    'lineage',
  ],
  properties: {
    schema_version: { const: 1 },
    intent_id: { $ref: '#/$defs/uuid' },
    correlation_id: { $ref: '#/$defs/uuid' },
    request_id: { $ref: '#/$defs/request_id' },
    idempotency_key: { $ref: '#/$defs/id_token' },
    canonical_gate_id: { $ref: '#/$defs/id_token' },
    event_kind: { enum: ['open', 'trim', 'close'] },
    event_sequence: { type: 'integer', minimum: 1 },
    gate_event_sequence: { type: 'integer', minimum: 1 },
    device_id: { $ref: '#/$defs/id_token' },
    adapter_gate_id: { $ref: '#/$defs/id_token' },
    capability_release_id: { $ref: '#/$defs/id_token' },
    capability_hash: { $ref: '#/$defs/sha256' },
    target_position_m: { $ref: '#/$defs/position_m' },
    target_level: { $ref: '#/$defs/target_level' },
    not_before: { $ref: '#/$defs/utc_instant' },
    deadline: { $ref: '#/$defs/utc_instant' },
    mode: {
      description:
        "REQUESTED mode; NOT an authority grant. Only 'shadow' is enabled. 'operator_approved' is state vocabulary that cannot execute — execution authority is a separate, dark-by-default gate owned by PR 7.x. A consumer MUST NOT treat this field as proof of approval.",
      enum: ['shadow', 'operator_approved'],
    },
    lineage: { $ref: '#/$defs/lineage' },
  },
  allOf: [
    {
      if: { properties: { event_kind: { const: 'close' } } },
      then: { properties: { target_position_m: { const: 0 } } },
    },
    {
      if: { properties: { event_kind: { enum: ['open', 'trim'] } } },
      then: { properties: { target_position_m: { type: 'number', exclusiveMinimum: 0 } } },
    },
  ],
  $defs: {
    uuid: {
      type: 'string',
      minLength: 36,
      maxLength: 36,
      pattern: '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$',
    },
    sha256: { type: 'string', minLength: 64, maxLength: 64, pattern: '^[0-9a-f]{64}$' },
    request_id: {
      type: 'string',
      minLength: 1,
      maxLength: 128,
      pattern: '^[A-Za-z0-9._-]{1,128}$',
    },
    id_token: { type: 'string', minLength: 1, maxLength: 128, pattern: '^[!-~]+$' },
    release_id: { type: 'string', minLength: 1, maxLength: 256, pattern: '^[!-~]+$' },
    utc_instant: {
      type: 'string',
      minLength: 20,
      maxLength: 27,
      pattern:
        '^[0-9]{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])T(0[0-9]|1[0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](\\.[0-9]{1,6})?Z$',
    },
    position_m: { type: 'number', minimum: 0, maximum: 1000 },
    target_level: { type: 'integer', minimum: 0, maximum: 65535 },
    lineage: {
      type: 'object',
      additionalProperties: false,
      required: [
        'campaign_id',
        'plan_id',
        'plan_version',
        'input_content_hash',
        'draft_content_hash',
        'requirement_run_id',
        'requirement_version',
        'requirement_set_sha256',
        'model_snapshot_id',
        'model_release_id',
        'model_release_content_hash',
        'prediction_run_id',
        'prediction_identity_version',
        'engine_descriptor_content_hash',
        'artifact_sha256',
      ],
      properties: {
        campaign_id: { $ref: '#/$defs/uuid' },
        plan_id: { $ref: '#/$defs/uuid' },
        plan_version: { type: 'integer', minimum: 1 },
        input_content_hash: { $ref: '#/$defs/sha256' },
        draft_content_hash: { $ref: '#/$defs/sha256' },
        requirement_run_id: { $ref: '#/$defs/uuid' },
        requirement_version: { type: 'integer', minimum: 1 },
        requirement_set_sha256: { $ref: '#/$defs/sha256' },
        model_snapshot_id: { $ref: '#/$defs/sha256' },
        model_release_id: { $ref: '#/$defs/release_id' },
        model_release_content_hash: { $ref: '#/$defs/sha256' },
        prediction_run_id: { $ref: '#/$defs/sha256' },
        prediction_identity_version: { const: 2 },
        engine_descriptor_content_hash: { $ref: '#/$defs/sha256' },
        artifact_sha256: { $ref: '#/$defs/sha256' },
      },
    },
  },
} as const;
