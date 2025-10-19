const { describe, it, expect } = require('@jest/globals');

jest.mock('child_process', () => ({
  spawn: jest.fn(() => ({ stdout: { on: jest.fn() }, stderr: { on: jest.fn() }, on: jest.fn(), kill: jest.fn() }))
}));

describe('start-smartfarm-workers', () => {
  it('spawns three workers with expected env flags', () => {
    const { spawn } = require('child_process');
    const { startWorkers } = require('../../../scripts/start-smartfarm-workers');
    startWorkers();
    expect(spawn).toHaveBeenCalledTimes(3);
    const calls = spawn.mock.calls.map(c => ({ cmd: c[0], args: c[1], env: c[2].env }));
    expect(calls[0].args[0]).toContain('start-zip-watcher.js');
    expect(calls[0].env.ZIP_WATCH_DIR).toBe('/datauploads');
    expect(calls[1].args[0]).toContain('run-waterlevel-listener.js');
    expect(calls[1].env.WL_LISTEN).toBe('true');
    expect(calls[2].args[0]).toContain('listen-worker.js');
    expect(calls[2].env.ENABLE_DB_LISTENER).toBe('true');
  });
});