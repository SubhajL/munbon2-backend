# PR 6.1b — Approved Field Device & Quantizer Artifact (SYNTHESIS PLAN)

**Service:** `services/scada-gate-control` (TypeScript, strict). Gate: `npm run typecheck && npm run lint && npm test`.
**Method:** g-planning (Claude plan + independent Plan-agent 2nd opinion, Codex out of tokens) → this synthesis.
**Baseline:** main `10711d2f`; scada 303 passed / 4 env-gated skips ×1 (green). No frozen 6.0 contract is edited.

## Overview
6.1b adds a NEW service-owned "approved field artifact" (rich: canonical gate + device/adapter +
register/unit + discrete quantizer + readback semantics + evidence refs + approval metadata +
approved lineage anchor) plus two pure functions: a generator `buildDeviceRegistryArtifact()` that
**projects** the rich artifact down to the EXACT endpoint-free `{capability_release_id, capabilities}`
document the 6.1a loader already consumes (byte-exact, deterministic, hash-idempotent), and a
validator `validateApprovedRegistryCoverage()` that fail-closed asserts exact approved-gate coverage,
quantizer monotonicity/bijectivity, readback round-trip separability, and endpoint/secret hygiene.
It also wires the reserved `lineage_mismatch` reason code into `validateCommandIntent` as an OPTIONAL,
dark-by-default, **reject-only** lineage anchor. D6 (per-gate actuator master) is unavailable ⇒ ship
software + a loudly-labeled non-field-approved EXAMPLE fixture only; the real artifact stays external,
and every new runtime path is dark by default so an un-configured SCADA behaves byte-identically to today.

## KEY DECISIONS
1. **Include `lineage_mismatch` in 6.1b, dark-by-default.** It is REJECT-ONLY: it can only turn a
   would-be accept into a reject; it grants nothing, so it cannot leak authority into 7.1a's territory.
   The 6.2 plan reserved it "for 6.1b"; the frozen receipt enum already contains it (no contract change).
2. **Anchor pins 3 fields: `{model_release_id, model_release_content_hash, engine_descriptor_content_hash}`.**
   The "approved commandable release" compute identity — stable across plan versions, matching 7.1a's
   "grant binds model release/hash". EXCLUDE `artifact_sha256`/`prediction_run_id`/`campaign_id`/`plan_*`/
   `requirement_*`: those churn per campaign/plan/run; pinning them conflates device+model approval with
   per-plan approval (7.x). (2nd-opinion proposed 4 fields incl. `artifact_sha256`; rejected — per-run.)
   A FIXED 3-field object (not a free subset map) avoids the empty-`{}`-matches-everything footgun.
3. **Ordering = position 4:** freshness → capability → target → **lineage** → window → deadline. PURELY
   ADDITIVE: every existing 6.2 precedence is preserved (stale → `freshness_failed`, absent gate →
   `capability_mismatch`, non-member → `target_invalid`); lineage (a static authority defect) only beats
   transient timing. `validateCommandIntent(intent, snapshot, nowMs, anchor: ApprovedLineageAnchor | null = null)`
   — the 4th arg defaults to null, so all existing 3-arg call sites/tests are byte-identical.
4. **Dark-by-default loader.** `SCADA_APPROVED_LINEAGE_ANCHOR_PATH` unset/blank → `null` → no lineage
   check (identical to 6.2). Set-but-broken/oversized/malformed/hygiene-violating → THROW at startup
   (fail-fast, mirrors 6.1a's registry loader; opting in is deliberate, failing OPEN would silently
   disable the check).
5. **No frozen-contract churn.** The artifact schema is EMBEDDED (`as const`), NOT added under
   `contracts/machine-boundary/v1/` (that would change `manifest.json:contract_set_sha256` =
   frozen `MACHINE_BOUNDARY_CONTRACT_SET_SHA256`). New types live in the new domain file; `machine-boundary.ts`
   stays the pure frozen mirror.
6. **The rich artifact is NEVER loaded into the SCADA runtime process.** Operator runs the pure generator
   OFFLINE to produce the two small env inputs (the projected registry for `SCADA_DEVICE_REGISTRY_PATH`,
   and the small anchor JSON for `SCADA_APPROVED_LINEAGE_ANCHOR_PATH`). Register/unit/readback/evidence/
   approval never reach the runtime snapshot or its hash.

## Approved field artifact shape (embedded APPROVED_FIELD_ARTIFACT_SCHEMA_V1, `additionalProperties:false`)
```jsonc
{
  "artifact_version": 1,
  "capability_release_id": "<id_token>",            // projects straight to the runtime registry
  "approval": {                                      // approval metadata (roles/refs, NO secrets/PII)
    "scope": "pilot" | "all-gate",
    "approved_by_role": "<string>",                  // a ROLE, never a person's credential
    "approved_at": "<utc_instant>",
    "approval_reference": "<string>",                // committed EXAMPLE must contain /EXAMPLE/i
    "evidence": [ { "kind": "<string>", "reference": "<string>", "sha256": "<64hex>" } ]
  },
  "approved_lineage_anchor": {                        // the 3-field anchor (Decision 2)
    "model_release_id": "<release_id>",
    "model_release_content_hash": "<64hex>",
    "engine_descriptor_content_hash": "<64hex>"
  },
  "gates": [
    {
      "canonical_gate_id": "<id_token>",
      "device_id": "<id_token>", "adapter_gate_id": "<id_token>",
      "register": { "unit_id": <int>, "command_register": <int>, "readback_register": <int> },  // Modbus map (not a secret); projected away
      "readback": { "tolerance_m": <number>0>, "settle_ms": <int>=0> },                           // readback semantics for round-trip + 6.3
      "quantizer": { "targets": [ { "target_position_m": <number>=0>, "target_level": <int 0..65535> } ] },
      "evidence": [ { "kind": "<string>", "reference": "<string>", "sha256": "<64hex>" } ]
    }
  ]
}
```
Committed to repo = ONLY `src/domain/__fixtures__/approved-field-artifact.example.json` (approval_reference
carries an `EXAMPLE` marker; a spec asserts it). Real artifact = external. Runtime env inputs are the two
small projections, never this file.

## Files
NEW (`services/scada-gate-control/`):
- `src/domain/approved-field-artifact.schema.ts` — `APPROVED_FIELD_ARTIFACT_SCHEMA_V1` + `APPROVED_LINEAGE_ANCHOR_SCHEMA_V1` (`as const`), shared `$defs` (sha256/id_token/utc_instant/release_id).
- `src/domain/approved-field-artifact.ts` — types + `buildDeviceRegistryArtifact`, `validateApprovedRegistryCoverage`, `extractApprovedLineageAnchor`, `loadApprovedLineageAnchor`, and private helpers `parseApprovedFieldArtifact`, `assertQuantizerMonotone`, `assertReadbackSeparable`, `quantizerRoundTrips`, `assertArtifactHygiene`.
- `src/domain/approved-field-artifact.spec.ts` — coverage/quantizer/readback/byte-exact/hygiene/anchor-extraction/loader tests.
- `src/domain/__fixtures__/approved-field-artifact.example.json` — the labeled non-production example.

CHANGE:
- `src/domain/command-intent-validation.ts` — optional 4th param + position-4 lineage check + pure `lineageMatchesAnchor`; rewrite the "reserved dead code" doc (lines 14-16).
- `src/domain/command-intent-validation.spec.ts` — anchor on/off, per-field mismatch, ordering tests.
- `src/api/routes.ts` — `ApiDeps.approvedLineageAnchor: ApprovedLineageAnchor | null`.
- `src/api/internal-routes.ts` — extend `InternalDeps` Pick; pass anchor as 4th arg at line 109.
- `src/index.ts` — `loadApprovedLineageAnchor()` (fail-fast when configured), pass to `buildServer`; dark-default warn when null.
- `services/scada-gate-control/CLAUDE.md` — document the env, offline projection tool, dark default, D6-blocked note.

NOT changed (verified): `server.ts` (spreads one `deps` into both routers), all frozen contracts, `capability-hash.ts`, `canonical-hash.ts`.

## Functions (signatures)
- `buildDeviceRegistryArtifact(approved: ApprovedFieldArtifact): DeviceRegistryDocument` — projects to EXACTLY `{capability_release_id, capabilities:{[gate]:{device_id,adapter_gate_id,targets}}}`; gates sorted by `canonical_gate_id`, targets sorted by `target_level` asc → byte-exact, hash-idempotent.
- `validateApprovedRegistryCoverage(approved: ApprovedFieldArtifact, expectedApprovedGateIds: ReadonlySet<string>): void` — throws unless gate set == expected exactly, every quantizer monotone+bijective+readback-separable+round-trips, and no endpoint/secret/host/proto key present.
- `extractApprovedLineageAnchor(approved: ApprovedFieldArtifact): ApprovedLineageAnchor` — pure projection of the 3 anchor fields; keeps the artifact the single source so the offline anchor JSON can't silently drift.
- `loadApprovedLineageAnchor(env?): ApprovedLineageAnchor | null` — dark-by-default runtime loader (size-capped, Ajv-validated, hygiene-checked); null when unset, throw when set-but-broken.
- `lineageMatchesAnchor(lineage: CommandLineage, anchor: ApprovedLineageAnchor): boolean` — exact equality on the 3 pinned fields.
- helpers: `assertQuantizerMonotone` (strictly increasing position ⇒ strictly increasing level, injective both ways), `assertReadbackSeparable(targets, toleranceM)` (adjacent positions differ by > 2×tolerance), `quantizerRoundTrips` (level→position→level & position→level→position identity on the discrete set).
- `validateCommandIntent(intent, snapshot, nowMs, anchor = null)` — position-4 lineage check.

## Tests (name — behavior)
Required: `registry covers exact approved gate scope` (extra/missing rejected); `quantizer monotone + round-trips readback`; `artifact regenerates byte-exactly` (stable capability_hash).
Quantizer/readback: rejects two-positions→one-level; rejects adjacent targets closer than 2×tolerance; level↔position round-trip identity; projected hash idempotent; projected registry loads clean through `loadDeviceCapabilitySnapshot`; projection drops register/readback/evidence (only 3 keys).
Hygiene: rejects `://`/`@` in any value; rejects host/ip/password/secret/token key anywhere; rejects `__proto__`/`constructor` gate key; committed example carries the EXAMPLE marker.
Anchor (command-intent-validation.spec.ts): accepts matching intent with anchor on; parameterized `lineage_mismatch` per pinned field; anchor-null ⇒ byte-identical to 6.2; stale+wrong-lineage → `freshness_failed` (not lineage); absent-gate+wrong-lineage → `capability_mismatch`; expired+wrong-lineage → `lineage_mismatch` (authority beats timing); `extractApprovedLineageAnchor` round-trips with the loaded anchor JSON; loader null-when-unset + throw-on-broken.
Schema: example validates against `APPROVED_FIELD_ARTIFACT_SCHEMA_V1`; malformed rejected.

## Wiring verification
| Component | Runtime entry | Registration | Config/deps/index |
|---|---|---|---|
| `buildDeviceRegistryArtifact` / `validateApprovedRegistryCoverage` / `extractApprovedLineageAnchor` | OFFLINE tool + specs | pure, exported | none (not runtime-wired) |
| `APPROVED_FIELD_ARTIFACT_SCHEMA_V1` | Ajv compile in domain | import | none |
| `loadApprovedLineageAnchor` | `index.ts main()` startup | result → `buildServer` deps | index.ts YES |
| `ApiDeps.approvedLineageAnchor` | `buildServer`→`buildInternalRouter` | `ApiDeps` + `InternalDeps` Pick | deps YES; server.ts NO edit |
| `validateCommandIntent` 4th arg | `/internal/v1/command-intents/validate` handler | `internal-routes.ts:109` | none |

DARK path (default): env unset → loader `null` → deps `null` → `validateCommandIntent(...,null)` → position-4 no-op → verdicts byte-identical to 6.2.

## Risks / rollback
- Fake-approval (highest): example-only + `EXAMPLE` marker spec + `expectedApprovedGateIds` is a caller/test arg, never a committed constant. Rollback: delete new files.
- Scope-creep into 7.1a: anchor is reject-only + 3 software-provenance fields + dark-by-default; NO accept/execute path; the config knob is a mechanism, not an authorization (7.1a owns turning it on).
- Cross-language hash drift: reuse `computeCapabilityHash`/`canonicalize`; one canonical target order; asserted by idempotency + `loadDeviceCapabilitySnapshot` tests.
- Boot-brick: fail-fast anchor can brick boot IF configured-and-broken (accepted; unset = dark = no risk). Rollback: unset the env.
- Everything is behind an unset env (dark) and the pure fns are unreferenced by index.ts; revert = delete new files + the ~4-line validate/deps/index diffs.
