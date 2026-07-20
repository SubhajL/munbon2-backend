import { mkdtempSync, writeFileSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';

import { describe, expect, it } from 'vitest';

import { readCappedJsonFile } from './capped-json-file';

const MSGS = { unreadable: 'unreadable-msg', tooBig: 'too-big-msg', notJson: 'not-json-msg' };
function tmp(body: string): string {
  const dir = mkdtempSync(join(tmpdir(), 'capped-json-'));
  const p = join(dir, 'f.json');
  writeFileSync(p, body);
  return p;
}

class CustomError extends Error {}

describe('readCappedJsonFile', () => {
  it('parses a valid JSON file under the cap', () => {
    expect(readCappedJsonFile(tmp('{"a":1}'), 1024, MSGS)).toEqual({ a: 1 });
  });

  it('throws the unreadable message when the file does not exist', () => {
    expect(() => readCappedJsonFile('/no/such/file.json', 1024, MSGS)).toThrow(/unreadable-msg/);
  });

  it('throws the tooBig message when the file exceeds the cap (before reading it)', () => {
    expect(() => readCappedJsonFile(tmp('{"a":1}'), 3, MSGS)).toThrow(/too-big-msg/);
  });

  it('throws the notJson message on malformed JSON', () => {
    expect(() => readCappedJsonFile(tmp('{nope'), 1024, MSGS)).toThrow(/not-json-msg/);
  });

  it('uses the supplied error factory for the thrown type', () => {
    try {
      readCappedJsonFile('/no/such/file.json', 1024, MSGS, (m) => new CustomError(m));
      throw new Error('should have thrown');
    } catch (err) {
      expect(err).toBeInstanceOf(CustomError);
    }
  });
});
