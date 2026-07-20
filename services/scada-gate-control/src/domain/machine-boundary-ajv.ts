import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';

/**
 * The single Ajv 2020 configuration for every machine-boundary (PR 6.0/6.1a/6.2)
 * validator: `strict` (unknown keywords/formats are errors), `allErrors`, and
 * `validateFormats` with the format plugins installed. Consolidated so the device
 * registry, the command-intent validator, and the receipt self-check can never drift
 * to different strictness — a payload rejected by one boundary validator must be
 * rejected by all (root CLAUDE.md: no forked implementations).
 */
export function newMachineBoundaryAjv(): Ajv2020 {
  const ajv = new Ajv2020({ strict: true, allErrors: true, validateFormats: true });
  addFormats(ajv);
  return ajv;
}
