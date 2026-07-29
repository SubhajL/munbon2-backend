# RID administrative irrigation calendar — contract v1

This contract separates two concepts that must not be conflated:

1. the fixed administrative irrigation year/week; and
2. source-driven crop activity for an actual planting and harvest window.

It is published as data because this repository has no runtime code-sharing path across its
Python and JavaScript service images. Each language-local implementation embeds the contract-set
SHA-256 and replays the same vectors.

## Public domain operations

The contract has four operations:

1. `irrigation_year(date) -> IrrigationYear`
2. `irrigation_week(date) -> IrrigationWeek`
3. `irrigation_week_span(IrrigationWeek) -> DateSpan`
4. `crop_activity(planting_date, expected_harvest_date, date) -> CropActivity`

`IrrigationYear` carries both Common Era (`ce`) and Buddhist Era (`be`) values. The invariant is
`be = ce + 543`; a bare ambiguous year integer is not a public identity.
Its `from_ce` / `from_be` constructors (JavaScript: `fromCe` / `fromBe`) convert an unambiguous
era value into the paired identity. These are constructors for the result type, not additional
calendar operations.

## Administrative irrigation year and week

1. An irrigation year runs from 1 November through 31 October.
2. It uses the ending-year label. The date 2024-11-01 is irrigation year 2025 CE / 2568 BE.
3. Weeks 1 through 52 are seven days. Week 53 is the one- or two-day remainder ending 31 October.
4. The start weekday drifts. These weeks are not ISO-8601 weeks.
5. The key is `YYYY-Rww`, using the CE ending-year label. The `R` distinguishes it from an ISO
   `YYYY-Www` key.

## Source-driven crop activity

Crop activity is not inferred from a fixed rainy/dry boundary. Munbon zones receive actual
planting dates from the planning frontend, and expected harvest is supplied or derived from crop
configuration.

- Before planting: `state = not_planted`, `crop_week = null`.
- Planting through expected harvest, inclusive: `state = active`, with week 1 on days 0–6.
- After expected harvest: `state = harvested`, `crop_week = null`.
- An expected harvest before planting is invalid.

A caller must make the crop-activity decision before ROS, AquaCrop, or any other demand engine.
The contract does not publish `season(date)` because a date alone cannot identify a zone's
operational crop cycle.

## Why ISO fields appear in the vectors

Irrigation-week vectors record ISO week/year only as contrast. For example, 2024-10-31 and
2024-11-01 are both ISO 2024-W44 but belong to different administrative irrigation years.

## Consumers

| Language   | Implementation                                         | Conformance test                          |
| ---------- | ------------------------------------------------------ | ----------------------------------------- |
| Python     | `services/bff-water-planning/src/core/rid_calendar.py` | `tests/unit/test_rid_calendar_vectors.py` |
| JavaScript | `services/ros/src/utils/rid-calendar.js`               | `tests/unit/rid-calendar.test.js`         |

Both suites normalize CRLF to LF before hashing contract bytes.

## Scope limit

Publishing this contract does not reinterpret existing database keys:

> These are existing legacy calendar keys with historical data and active writers. Their meaning
> must not be changed in place.

The existing `calendar_week` / `calendar_year` tuples and planning-depth `YYYY-Www` keys remain
unchanged. Any later cutover requires an explicit discriminator, historical audit, and backfill.

This contract also does not repair or activate the dormant ROS workbook-upload path. Workbook
family semantics, paddy-row parsing, season input, queue plumbing, and a non-empty real-workbook
assertion belong in a separate vertical slice.
