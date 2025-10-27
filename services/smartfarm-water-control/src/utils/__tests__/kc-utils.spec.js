'use strict';

const { tokenizeCropType } = require('../kc-utils');

describe('kc-utils.tokenizeCropType', () => {
  test('tokenizeCropType_splits_and_deduplicates_tokens', () => {
    const input = 'ทุเรียน  กล้วย  กล้วย';
    const tokens = tokenizeCropType(input);
    expect(tokens).toEqual(['ทุเรียน', 'กล้วย']);
  });

  test('tokenizeCropType_handles_empty_and_non_string', () => {
    expect(tokenizeCropType(/** @type any */ (null))).toEqual([]);
    expect(tokenizeCropType(/** @type any */ (undefined))).toEqual([]);
    expect(tokenizeCropType(/** @type any */ (42))).toEqual([]);
    expect(tokenizeCropType('   ')).toEqual([]);
  });
});