import { existsSync, readFileSync } from 'fs';
import { dirname, join } from 'path';

import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { describe, expect, it } from 'vitest';

import {
  buildValidationReceipt,
  compileCommandIntentValidator,
  formatUtcInstant,
  parseUtcInstant,
  validateCommandIntent,
} from './command-intent-validation';
import type { ApprovedLineageAnchor } from './approved-field-artifact';
import type { CommandIntent, DeviceCapabilitySnapshot } from './machine-boundary';
import { intentContentHash } from './intent-content-hash';
import { VALIDATION_RECEIPT_SCHEMA_V1 } from './validation-receipt.schema';

function fixture(rel: string): unknown {
  let dir = __dirname;
  for (let i = 0; i < 8; i += 1) {
    const candidate = join(dir, 'contracts', 'machine-boundary', 'v1', rel);
    if (existsSync(candidate)) return JSON.parse(readFileSync(candidate, 'utf-8'));
    dir = dirname(dir);
  }
  throw new Error(`fixture not found: ${rel}`);
}

const BASE_INTENT = fixture('fixtures/valid/command-intent.shadow.valid.json') as CommandIntent;

// A snapshot whose one gate binding exactly matches BASE_INTENT.
const MATCHING_SNAPSHOT = {
  schema_version: 1,
  capability_release_id: 'cap-2026-07-19-a',
  capability_hash: 'a'.repeat(64),
  capabilities: {
    'M(0,0;1,0)': {
      device_id: 'scada-rtu-07',
      adapter_gate_id: 'ch3',
      targets: [
        { target_position_m: 0.2, target_level: 1 },
        { target_position_m: 0.45, target_level: 3 },
      ],
    },
  },
} as unknown as DeviceCapabilitySnapshot;

const IN_WINDOW = Date.parse('2026-07-20T03:00:00Z'); // between not_before and deadline
const intent = (over: Partial<CommandIntent>): CommandIntent => ({ ...BASE_INTENT, ...over });

describe('validateCommandIntent', () => {
  it('accepts a fully-matching in-window shadow intent', () => {
    expect(validateCommandIntent(BASE_INTENT, MATCHING_SNAPSHOT, IN_WINDOW)).toEqual({
      status: 'validation_accepted',
      reason_code: null,
    });
  });

  it('rejects freshness_failed when the intent pins a different capability_release_id', () => {
    expect(
      validateCommandIntent(
        intent({ capability_release_id: 'cap-old' }),
        MATCHING_SNAPSHOT,
        IN_WINDOW,
      ),
    ).toEqual({ status: 'validation_rejected', reason_code: 'freshness_failed' });
  });

  it('rejects freshness_failed when the intent pins a different capability_hash', () => {
    expect(
      validateCommandIntent(
        intent({ capability_hash: 'b'.repeat(64) }),
        MATCHING_SNAPSHOT,
        IN_WINDOW,
      ),
    ).toEqual({ status: 'validation_rejected', reason_code: 'freshness_failed' });
  });

  it('rejects every real intent as freshness_failed against the dark/empty snapshot', () => {
    const empty = {
      schema_version: 1,
      capability_release_id: '__empty__',
      capability_hash: 'c'.repeat(64),
      capabilities: {},
    } as unknown as DeviceCapabilitySnapshot;
    expect(validateCommandIntent(BASE_INTENT, empty, IN_WINDOW).reason_code).toBe(
      'freshness_failed',
    );
  });

  it('rejects capability_mismatch when the gate is absent from the snapshot', () => {
    expect(
      validateCommandIntent(
        intent({ canonical_gate_id: 'M(9,9;9,9)' }),
        MATCHING_SNAPSHOT,
        IN_WINDOW,
      ),
    ).toEqual({ status: 'validation_rejected', reason_code: 'capability_mismatch' });
  });

  it('rejects capability_mismatch when device_id disagrees with the snapshot binding', () => {
    expect(
      validateCommandIntent(intent({ device_id: 'scada-rtu-99' }), MATCHING_SNAPSHOT, IN_WINDOW)
        .reason_code,
    ).toBe('capability_mismatch');
  });

  it('rejects capability_mismatch when adapter_gate_id disagrees', () => {
    expect(
      validateCommandIntent(intent({ adapter_gate_id: 'ch9' }), MATCHING_SNAPSHOT, IN_WINDOW)
        .reason_code,
    ).toBe('capability_mismatch');
  });

  it('does NOT let a prototype gate id read a phantom capability', () => {
    expect(
      validateCommandIntent(
        intent({ canonical_gate_id: '__proto__' }),
        MATCHING_SNAPSHOT,
        IN_WINDOW,
      ).reason_code,
    ).toBe('capability_mismatch');
  });

  it('rejects target_invalid when the position is not a snapshot member', () => {
    // 0.9 is not one of the gate targets; open requires >0 so it stays schema-valid.
    expect(
      validateCommandIntent(intent({ target_position_m: 0.9 }), MATCHING_SNAPSHOT, IN_WINDOW)
        .reason_code,
    ).toBe('target_invalid');
  });

  it('rejects target_invalid when the level disagrees with the matched position', () => {
    expect(
      validateCommandIntent(intent({ target_level: 4 }), MATCHING_SNAPSHOT, IN_WINDOW).reason_code,
    ).toBe('target_invalid');
  });

  it('rejects not_before_violation when not_before is after the deadline', () => {
    expect(
      validateCommandIntent(
        intent({ not_before: '2026-07-20T07:00:00Z' }),
        MATCHING_SNAPSHOT,
        IN_WINDOW,
      ).reason_code,
    ).toBe('not_before_violation');
  });

  it.each([
    ['2026-02-30T00:00:00Z'], // Feb has no 30th
    ['2026-04-31T00:00:00Z'], // April has no 31st
    ['2026-02-29T00:00:00Z'], // 2026 is not a leap year
  ])(
    'rejects a calendar-impossible not_before (%s) instead of silently rolling it over',
    (badDate) => {
      // Regression for the Date.parse rollover bug: these pass the 6.0 regex but must
      // NOT be accepted with a shifted window.
      expect(
        validateCommandIntent(intent({ not_before: badDate }), MATCHING_SNAPSHOT, IN_WINDOW),
      ).toEqual({ status: 'validation_rejected', reason_code: 'not_before_violation' });
    },
  );

  it('rejects deadline_expired when now is past the deadline', () => {
    const past = Date.parse('2026-07-20T09:00:00Z');
    expect(validateCommandIntent(BASE_INTENT, MATCHING_SNAPSHOT, past).reason_code).toBe(
      'deadline_expired',
    );
  });

  it('accepts a future-dated intent whose window has not opened (validation never acts)', () => {
    const beforeWindow = Date.parse('2026-07-19T00:00:00Z');
    expect(validateCommandIntent(BASE_INTENT, MATCHING_SNAPSHOT, beforeWindow).status).toBe(
      'validation_accepted',
    );
  });

  it('checks freshness before capability (stale release beats an absent gate)', () => {
    expect(
      validateCommandIntent(
        intent({ capability_release_id: 'cap-old', canonical_gate_id: 'M(9,9;9,9)' }),
        MATCHING_SNAPSHOT,
        IN_WINDOW,
      ).reason_code,
    ).toBe('freshness_failed');
  });
});

describe('validateCommandIntent with an approved lineage anchor (PR 6.1b)', () => {
  // Matches BASE_INTENT's lineage (the shadow.valid fixture).
  const ANCHOR: ApprovedLineageAnchor = {
    model_release_id: 'engineering-prior-v3-v1',
    model_release_content_hash: '5'.repeat(64),
    engine_descriptor_content_hash: '7'.repeat(64),
  };
  const wrongLineage = (over: Partial<CommandIntent['lineage']>): CommandIntent =>
    intent({ lineage: { ...BASE_INTENT.lineage, ...over } });

  it('with anchor null, behaves identically to 6.2 (accepts, never lineage_mismatch)', () => {
    expect(validateCommandIntent(BASE_INTENT, MATCHING_SNAPSHOT, IN_WINDOW, null)).toEqual({
      status: 'validation_accepted',
      reason_code: null,
    });
    // The default 3-arg call is also a no-op anchor.
    expect(validateCommandIntent(BASE_INTENT, MATCHING_SNAPSHOT, IN_WINDOW).reason_code).toBeNull();
  });

  it('accepts an intent whose lineage matches the configured anchor', () => {
    expect(validateCommandIntent(BASE_INTENT, MATCHING_SNAPSHOT, IN_WINDOW, ANCHOR)).toEqual({
      status: 'validation_accepted',
      reason_code: null,
    });
  });

  it.each([
    ['model_release_id', { model_release_id: 'engineering-prior-v9-v1' }],
    ['model_release_content_hash', { model_release_content_hash: 'a'.repeat(64) }],
    ['engine_descriptor_content_hash', { engine_descriptor_content_hash: 'b'.repeat(64) }],
  ])('rejects lineage_mismatch when %s differs from the anchor', (_f, over) => {
    expect(
      validateCommandIntent(wrongLineage(over), MATCHING_SNAPSHOT, IN_WINDOW, ANCHOR).reason_code,
    ).toBe('lineage_mismatch');
  });

  it('does NOT pin per-plan fields: a new plan_id/prediction_run_id still validates', () => {
    const nextVersion = intent({
      lineage: {
        ...BASE_INTENT.lineage,
        plan_id: 'cccccccc-cccc-4ccc-8ccc-cccccccccccc',
        plan_version: 2,
        prediction_run_id: 'd'.repeat(64),
        artifact_sha256: 'e'.repeat(64),
      },
    });
    expect(
      validateCommandIntent(nextVersion, MATCHING_SNAPSHOT, IN_WINDOW, ANCHOR).reason_code,
    ).toBeNull();
  });

  it('reports freshness_failed (not lineage_mismatch) for a stale intent with wrong lineage', () => {
    const staleWrong = intent({
      capability_release_id: 'cap-old',
      lineage: { ...BASE_INTENT.lineage, model_release_id: 'unapproved-v1' },
    });
    expect(
      validateCommandIntent(staleWrong, MATCHING_SNAPSHOT, IN_WINDOW, ANCHOR).reason_code,
    ).toBe('freshness_failed');
  });

  it('reports capability_mismatch (not lineage_mismatch) for an absent gate with wrong lineage', () => {
    const absentWrong = intent({
      canonical_gate_id: 'M(9,9;9,9)',
      lineage: { ...BASE_INTENT.lineage, model_release_id: 'unapproved-v1' },
    });
    expect(
      validateCommandIntent(absentWrong, MATCHING_SNAPSHOT, IN_WINDOW, ANCHOR).reason_code,
    ).toBe('capability_mismatch');
  });

  it('reports lineage_mismatch (not deadline_expired) for a wrong-lineage expired intent', () => {
    const past = Date.parse('2026-07-20T09:00:00Z');
    const wrong = wrongLineage({ model_release_id: 'unapproved-v1' });
    // Without an anchor this same intent would report deadline_expired (position 6)...
    expect(validateCommandIntent(wrong, MATCHING_SNAPSHOT, past).reason_code).toBe(
      'deadline_expired',
    );
    // ...but with the anchor the position-4 lineage check fires first.
    expect(validateCommandIntent(wrong, MATCHING_SNAPSHOT, past, ANCHOR).reason_code).toBe(
      'lineage_mismatch',
    );
  });

  it('a matching-lineage intent is still subject to deadline_expired', () => {
    const past = Date.parse('2026-07-20T09:00:00Z');
    expect(validateCommandIntent(BASE_INTENT, MATCHING_SNAPSHOT, past, ANCHOR).reason_code).toBe(
      'deadline_expired',
    );
  });
});

describe('compileCommandIntentValidator', () => {
  it('accepts the valid shadow fixture and rejects an unknown-mode fixture', () => {
    const validate = compileCommandIntentValidator();
    expect(validate(BASE_INTENT)).toBe(true);
    expect(validate(fixture('fixtures/invalid/command-intent.unknown-mode.invalid.json'))).toBe(
      false,
    );
  });
});

describe('buildValidationReceipt', () => {
  const receiptValidator = (() => {
    const ajv = new Ajv2020({ strict: true, allErrors: true, validateFormats: true });
    addFormats(ajv);
    return ajv.compile(VALIDATION_RECEIPT_SCHEMA_V1 as unknown as Record<string, unknown>);
  })();

  it('builds an accepted receipt that satisfies the receipt v1 contract', () => {
    const receipt = buildValidationReceipt({
      intent: BASE_INTENT,
      verdict: { status: 'validation_accepted', reason_code: null },
      receiptId: '99999999-9999-4999-8999-999999999999',
      validatedAt: formatUtcInstant(IN_WINDOW),
      contentHash: intentContentHash(BASE_INTENT),
    });
    expect(receiptValidator(receipt)).toBe(true);
    expect(receipt).toMatchObject({
      status: 'validation_accepted',
      reason_code: null,
      intent_id: BASE_INTENT.intent_id,
      idempotency_key: BASE_INTENT.idempotency_key,
      capability_hash: BASE_INTENT.capability_hash,
    });
  });

  it('builds a rejected receipt carrying the reason code', () => {
    const receipt = buildValidationReceipt({
      intent: BASE_INTENT,
      verdict: { status: 'validation_rejected', reason_code: 'freshness_failed' },
      receiptId: '99999999-9999-4999-8999-999999999999',
      validatedAt: formatUtcInstant(IN_WINDOW),
      contentHash: intentContentHash(BASE_INTENT),
    });
    expect(receiptValidator(receipt)).toBe(true);
    expect(receipt.reason_code).toBe('freshness_failed');
  });
});

describe('formatUtcInstant', () => {
  it('formats epoch ms as a contract UTC instant (trailing Z)', () => {
    expect(formatUtcInstant(Date.parse('2026-07-20T06:00:00Z'))).toBe('2026-07-20T06:00:00.000Z');
  });
});

describe('parseUtcInstant', () => {
  it('parses a real instant to its epoch ms', () => {
    expect(parseUtcInstant('2026-07-20T06:00:00Z')).toBe(Date.parse('2026-07-20T06:00:00Z'));
  });

  it('accepts a real leap day (2024-02-29)', () => {
    expect(parseUtcInstant('2024-02-29T00:00:00Z')).toBe(Date.parse('2024-02-29T00:00:00Z'));
  });

  it.each(['2026-02-30T00:00:00Z', '2026-04-31T00:00:00Z', '2026-02-29T00:00:00Z', 'not-a-date'])(
    'returns null for the calendar-impossible/malformed instant %s',
    (bad) => {
      expect(parseUtcInstant(bad)).toBeNull();
    },
  );
});
