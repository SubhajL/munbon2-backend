/** JavaScript conformance against the shared RID calendar contract bytes. */

const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

const {
  CONTRACT_SET_SHA256,
  IrrigationYear,
  cropActivity,
  irrigationWeek,
  irrigationWeekSpan,
  irrigationYear,
} = require('../../src/utils/rid-calendar');

const CONTRACTS = path.resolve(
  __dirname,
  '../../../../contracts/rid-calendar/v1',
);
const GROUPS = ['schemas', 'fixtures', 'documents'];
const REQUIRED_IRRIGATION_DATES = [
  '1900-11-01',
  '2024-02-29',
  '2024-10-31',
  '2024-11-01',
  '2025-10-31',
  '2025-11-01',
  '2401-10-31',
];
const REQUIRED_CROP_NOTES = [
  'day before planting',
  'planting day',
  'expected harvest day',
  'day after expected harvest',
];

const readJson = (name) =>
  JSON.parse(fs.readFileSync(path.join(CONTRACTS, name), 'utf8'));

const sha256 = (name) =>
  crypto
    .createHash('sha256')
    .update(
      Buffer.from(
        fs
          .readFileSync(path.join(CONTRACTS, name))
          .toString('binary')
          .replace(/\r\n/g, '\n'),
        'binary',
      ),
    )
    .digest('hex');

const manifest = readJson('manifest.json');
const entries = GROUPS.flatMap((group) => manifest[group]);

describe('rid-calendar contract pinning', () => {
  test('every pinned file still hashes to its manifest entry', () => {
    entries.forEach((entry) => {
      expect(sha256(entry.relative_path)).toBe(entry.sha256);
    });
  });

  test('the manifest set hash is recomputed from current file bytes', () => {
    const records = GROUPS.flatMap((group) =>
      manifest[group].map((entry) => {
        const record = {};
        Object.keys(entry)
          .filter((key) => key !== 'sha256')
          .forEach((key) => {
            record[key] = entry[key];
          });
        record.sha256 = sha256(entry.relative_path);
        return record;
      }),
    );
    const canonical = JSON.stringify(
      records.map((record) =>
        Object.keys(record)
          .sort()
          .reduce(
            (sorted, key) => Object.assign(sorted, { [key]: record[key] }),
            {},
          ),
      ),
    );
    expect(crypto.createHash('sha256').update(canonical).digest('hex')).toBe(
      manifest.contract_set_sha256,
    );
  });

  test('both implementations pin the same contract set', () => {
    const pythonSource = fs.readFileSync(
      path.resolve(
        __dirname,
        '../../../bff-water-planning/src/core/rid_calendar.py',
      ),
      'utf8',
    );
    const pinned = pythonSource.match(/CONTRACT_SET_SHA256 = "([0-9a-f]{64})"/);
    expect(pinned[1]).toBe(CONTRACT_SET_SHA256);
    expect(CONTRACT_SET_SHA256).toBe(manifest.contract_set_sha256);
  });
});

describe('contract integrity witnesses', () => {
  test('load-bearing irrigation and crop boundaries remain named', () => {
    const irrigationDates = new Set(
      readJson('irrigation-week.vectors.json').vectors.map(
        (vector) => vector.date,
      ),
    );
    const cropNotes = new Set(
      readJson('crop-activity.vectors.json').vectors.map(
        (vector) => vector.note,
      ),
    );

    expect(
      REQUIRED_IRRIGATION_DATES.every((date) => irrigationDates.has(date)),
    ).toBe(true);
    expect(REQUIRED_CROP_NOTES.every((note) => cropNotes.has(note))).toBe(true);
  });
});

describe('IrrigationYear', () => {
  test('converts either era to the same paired identity', () => {
    const expected = { ce: 2025, be: 2568 };

    expect(IrrigationYear.fromCe(2025)).toEqual(expected);
    expect(IrrigationYear.fromBe(2568)).toEqual(expected);
  });
});

describe('irrigationWeek', () => {
  const vectors = readJson('irrigation-week.vectors.json').vectors;

  test.each(vectors.map((vector) => [vector.date, vector]))(
    '%s matches the golden identity and span',
    (_date, vector) => {
      const identity = irrigationWeek(vector.date);
      const span = irrigationWeekSpan(identity);

      expect(identity).toEqual({
        irrigationYear: vector.irrigation_year,
        irrigationWeek: vector.irrigation_week,
        key: vector.week_key,
      });
      expect(irrigationYear(vector.date)).toEqual(vector.irrigation_year);
      expect(span).toEqual({
        start: vector.week_start,
        end: vector.week_end,
        lengthDays: vector.week_length_days,
      });
    },
  );

  test('uses an ending-year label across the November boundary', () => {
    expect(irrigationWeek('2024-10-31').key).toBe('2024-R53');
    expect(irrigationWeek('2024-11-01')).toMatchObject({
      irrigationYear: { ce: 2025, be: 2568 },
      irrigationWeek: 1,
      key: '2025-R01',
    });
  });

  test('rejects an instant that is not a civil date', () => {
    expect(() => irrigationWeek(new Date(Date.UTC(2024, 10, 1, 12)))).toThrow(
      RangeError,
    );
  });
});

describe('irrigationWeekSpan', () => {
  test('rejects an irrigation identity with mismatched CE and BE values', () => {
    expect(() =>
      irrigationWeekSpan({
        irrigationYear: { ce: 2025, be: 2567 },
        irrigationWeek: 1,
      }),
    ).toThrow(/matching CE and BE/i);
  });
});

describe('cropActivity', () => {
  const vectors = readJson('crop-activity.vectors.json').vectors;

  test.each(vectors.map((vector) => [vector.note, vector]))(
    '%s',
    (_note, vector) => {
      expect(
        cropActivity(
          vector.planting_date,
          vector.expected_harvest_date,
          vector.on,
        ),
      ).toEqual({
        state: vector.state,
        cropWeek: vector.crop_week,
      });
    },
  );

  test('rejects a harvest before planting', () => {
    expect(() =>
      cropActivity('2026-07-15', '2026-07-14', '2026-07-15'),
    ).toThrow(/harvest/i);
  });
});
