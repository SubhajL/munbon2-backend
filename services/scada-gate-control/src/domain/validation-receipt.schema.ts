/**
 * PR 6.2a — the validation-receipt v1 JSON Schema, EMBEDDED in the service.
 *
 * Single source of truth: `contracts/machine-boundary/v1/validation-receipt.schema.json`
 * (PR 6.0); `validation-receipt.schema.spec.ts` drift-guards this const against it.
 * Embedded for the same dist-only-deploy reason as the command-intent schema. Every
 * receipt the validate endpoint emits is self-checked against this schema before it is
 * returned/persisted, so SCADA can never issue a contract-violating receipt.
 */
export const VALIDATION_RECEIPT_SCHEMA_V1 = {
  $schema: 'https://json-schema.org/draft/2020-12/schema',
  $id: 'https://munbon.internal/contracts/machine-boundary/v1/validation-receipt.schema.json',
  title: 'MachineBoundaryValidationReceiptV1',
  description:
    "SCADA's structural acceptance/rejection of a command intent WITHOUT any Modbus write. Transport/internal errors are service failures, not receipts. Engine-independent patterns only.",
  type: 'object',
  additionalProperties: false,
  required: [
    'schema_version',
    'receipt_id',
    'intent_id',
    'correlation_id',
    'request_id',
    'idempotency_key',
    'intent_content_hash',
    'capability_hash',
    'status',
    'validated_at',
    'reason_code',
  ],
  properties: {
    schema_version: { const: 1 },
    receipt_id: { $ref: '#/$defs/uuid' },
    intent_id: { $ref: '#/$defs/uuid' },
    correlation_id: { $ref: '#/$defs/uuid' },
    request_id: { $ref: '#/$defs/request_id' },
    idempotency_key: { $ref: '#/$defs/id_token' },
    intent_content_hash: { $ref: '#/$defs/sha256' },
    capability_hash: { $ref: '#/$defs/sha256' },
    status: { enum: ['validation_accepted', 'validation_rejected'] },
    validated_at: { $ref: '#/$defs/utc_instant' },
    reason_code: {
      oneOf: [{ type: 'null' }, { $ref: '#/$defs/reason_code' }],
    },
  },
  allOf: [
    {
      if: { properties: { status: { const: 'validation_accepted' } } },
      then: { properties: { reason_code: { type: 'null' } } },
    },
    {
      if: { properties: { status: { const: 'validation_rejected' } } },
      then: { properties: { reason_code: { $ref: '#/$defs/reason_code' } } },
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
    utc_instant: {
      type: 'string',
      minLength: 20,
      maxLength: 27,
      pattern:
        '^[0-9]{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])T(0[0-9]|1[0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](\\.[0-9]{1,6})?Z$',
    },
    reason_code: {
      enum: [
        'schema_invalid',
        'capability_mismatch',
        'target_invalid',
        'not_before_violation',
        'deadline_expired',
        'lineage_mismatch',
        'freshness_failed',
        'idempotency_conflict',
      ],
    },
  },
} as const;
