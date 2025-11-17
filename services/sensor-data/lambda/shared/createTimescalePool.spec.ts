import { createTimescalePool } from './createTimescalePool';

jest.mock('pg', () => {
  const actual = jest.requireActual('pg');
  class FakePool {
    static instances = 0;
    constructor() { (FakePool as any).instances += 1; }
    on() { /* noop */ }
  }
  return { ...actual, Pool: FakePool };
});

describe('createTimescalePool', () => {
  test('returns a singleton Pool', () => {
    const p1 = createTimescalePool({ host: 'h', port: 5432, database: 'd', user: 'u' } as any);
    const p2 = createTimescalePool({ host: 'h', port: 5432, database: 'd', user: 'u' } as any);
    expect(p1).toBe(p2);
    // @ts-ignore
    expect((require('pg').Pool as any).instances).toBe(1);
  });
});

