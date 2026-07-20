import { readFileSync, statSync } from 'fs';

/**
 * The single fail-closed "read a size-capped JSON file" skeleton for every machine-boundary
 * FILE input (6.1a device registry, 6.1b lineage anchor). Consolidated so a future hardening
 * (symlink rejection, encoding handling, a different cap policy) lands in ONE place rather than
 * drifting between two forked loaders — root CLAUDE.md: "consolidate, don't fork".
 *
 * Bounds peak memory by checking `statSync().size` BEFORE reading the whole file into a string
 * (an oversized file would otherwise OOM during the read, before any cap could fire). Each
 * caller supplies its own exact messages and (optionally) its own Error subtype via `makeError`,
 * so callers keep their existing, test-pinned error strings/types.
 */
export function readCappedJsonFile(
  path: string,
  maxBytes: number,
  messages: { readonly unreadable: string; readonly tooBig: string; readonly notJson: string },
  makeError: (message: string) => Error = (m) => new Error(m),
): unknown {
  let sizeBytes: number;
  try {
    sizeBytes = statSync(path).size;
  } catch {
    throw makeError(messages.unreadable);
  }
  if (sizeBytes > maxBytes) {
    throw makeError(messages.tooBig);
  }

  let raw: string;
  try {
    raw = readFileSync(path, 'utf-8');
  } catch {
    throw makeError(messages.unreadable);
  }

  try {
    return JSON.parse(raw);
  } catch {
    throw makeError(messages.notJson);
  }
}
