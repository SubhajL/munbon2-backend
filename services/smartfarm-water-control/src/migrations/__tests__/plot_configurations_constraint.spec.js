const { describe, it, expect } = require('@jest/globals');
const { execSync } = require('child_process');

describe('plot_configurations crop_type allows garden', () => {
  it('runs migration script successfully', () => {
    const out = execSync('node scripts/migrations/allow-garden-croptype.js');
    expect(out.toString()).toMatch(/crop_type now allows garden/);
  });
});
