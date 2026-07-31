'use strict';

/** Administrative irrigation calendar and source-driven crop activity. */

const CONTRACT_SET_SHA256 =
  '987006c64402e79b9cb7af29358283f4cb368203cbd46935490a7ff453115539';

const ANCHOR_MONTH = 11;
const ANCHOR_DAY = 1;
const WEEKS_PER_IRRIGATION_YEAR = 53;
const MIN_IRRIGATION_YEAR_CE = 1901;
const MAX_IRRIGATION_YEAR_CE = 2401;
const BE_OFFSET = 543;
const MS_PER_DAY = 86400000;
const ISO_DATE = /^(\d{4})-(\d{2})-(\d{2})$/;

const pad = (value, width) => String(value).padStart(width, '0');

function toCivilDate(value, name) {
  if (value instanceof Date) {
    if (Number.isNaN(value.getTime())) {
      throw new RangeError(`${name} is an invalid Date`);
    }
    if (value.getTime() % MS_PER_DAY !== 0) {
      throw new RangeError(
        `${name} must be exactly UTC midnight; an instant is not a civil date`,
      );
    }
    return value.toISOString().slice(0, 10);
  }
  if (typeof value !== 'string') {
    throw new TypeError(
      `${name} must be a YYYY-MM-DD string or a UTC-midnight Date`,
    );
  }
  const match = ISO_DATE.exec(value);
  if (!match) {
    throw new RangeError(
      `${name} must be formatted YYYY-MM-DD, got ${JSON.stringify(value)}`,
    );
  }
  const [, year, month, day] = match.map(Number);
  const roundTrip = new Date(Date.UTC(year, month - 1, day));
  if (roundTrip.toISOString().slice(0, 10) !== value) {
    throw new RangeError(`${name} is not a real calendar date: ${value}`);
  }
  return value;
}

const toEpochDay = (civilDate) =>
  Date.UTC(
    ...civilDate
      .split('-')
      .map(Number)
      .map((part, index) => (index === 1 ? part - 1 : part)),
  ) / MS_PER_DAY;

const fromEpochDay = (epochDay) =>
  new Date(epochDay * MS_PER_DAY).toISOString().slice(0, 10);

function irrigationYearFromCe(ce) {
  if (!Number.isInteger(ce)) {
    throw new TypeError('irrigation year CE value must be an integer');
  }
  if (ce < MIN_IRRIGATION_YEAR_CE || ce > MAX_IRRIGATION_YEAR_CE) {
    throw new RangeError(
      `irrigation year CE ${ce} outside supported range ` +
        `${MIN_IRRIGATION_YEAR_CE}..${MAX_IRRIGATION_YEAR_CE}`,
    );
  }
  return Object.freeze({ ce, be: ce + BE_OFFSET });
}

function irrigationYearFromBe(be) {
  if (!Number.isInteger(be)) {
    throw new TypeError('irrigation year BE value must be an integer');
  }
  return irrigationYearFromCe(be - BE_OFFSET);
}

const IrrigationYear = Object.freeze({
  fromBe: irrigationYearFromBe,
  fromCe: irrigationYearFromCe,
});

function validateIrrigationYear(value) {
  if (
    !value ||
    !Number.isInteger(value.ce) ||
    !Number.isInteger(value.be) ||
    value.be !== value.ce + BE_OFFSET
  ) {
    throw new TypeError('irrigationYear must carry matching CE and BE values');
  }
  IrrigationYear.fromCe(value.ce);
}

function irrigationYearSpan(identity) {
  validateIrrigationYear(identity);
  return {
    start: `${pad(identity.ce - 1, 4)}-${pad(ANCHOR_MONTH, 2)}-${pad(
      ANCHOR_DAY,
      2,
    )}`,
    end: `${pad(identity.ce, 4)}-10-31`,
  };
}

function irrigationYear(day) {
  const civilDate = toCivilDate(day, 'day');
  const [year, month, dayOfMonth] = civilDate.split('-').map(Number);
  const endingYear =
    month > ANCHOR_MONTH || (month === ANCHOR_MONTH && dayOfMonth >= ANCHOR_DAY)
      ? year + 1
      : year;
  return IrrigationYear.fromCe(endingYear);
}

function irrigationWeek(day) {
  const civilDate = toCivilDate(day, 'day');
  const year = irrigationYear(civilDate);
  const offset =
    toEpochDay(civilDate) - toEpochDay(irrigationYearSpan(year).start);
  const week = Math.floor(offset / 7) + 1;
  return Object.freeze({
    irrigationYear: year,
    irrigationWeek: week,
    key: `${pad(year.ce, 4)}-R${pad(week, 2)}`,
  });
}

function irrigationWeekSpan(week) {
  if (
    !week ||
    !Number.isInteger(week.irrigationWeek) ||
    week.irrigationWeek < 1 ||
    week.irrigationWeek > WEEKS_PER_IRRIGATION_YEAR
  ) {
    throw new RangeError(
      `irrigationWeek must be within 1..${WEEKS_PER_IRRIGATION_YEAR}`,
    );
  }
  const yearSpan = irrigationYearSpan(week.irrigationYear);
  const start = fromEpochDay(
    toEpochDay(yearSpan.start) + 7 * (week.irrigationWeek - 1),
  );
  const end = fromEpochDay(
    Math.min(toEpochDay(start) + 6, toEpochDay(yearSpan.end)),
  );
  return {
    start,
    end,
    lengthDays: toEpochDay(end) - toEpochDay(start) + 1,
  };
}

function cropActivity(plantingDate, expectedHarvestDate, on) {
  const planting = toCivilDate(plantingDate, 'plantingDate');
  const harvest = toCivilDate(expectedHarvestDate, 'expectedHarvestDate');
  const observed = toCivilDate(on, 'on');
  const plantingDay = toEpochDay(planting);
  const harvestDay = toEpochDay(harvest);
  const observedDay = toEpochDay(observed);

  if (harvestDay < plantingDay) {
    throw new RangeError(
      'expected harvest date must not precede planting date',
    );
  }
  if (observedDay < plantingDay) {
    return { state: 'not_planted', cropWeek: null };
  }
  if (observedDay > harvestDay) {
    return { state: 'harvested', cropWeek: null };
  }
  return {
    state: 'active',
    cropWeek: Math.floor((observedDay - plantingDay) / 7) + 1,
  };
}

module.exports = {
  CONTRACT_SET_SHA256,
  IrrigationYear,
  cropActivity,
  irrigationWeek,
  irrigationWeekSpan,
  irrigationYear,
};
