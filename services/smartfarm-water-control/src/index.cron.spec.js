describe('cron scheduling (gated)', () => {
  function makeCronStub() {
    const calls = [];
    return {
      calls,
      schedule: (pattern, fn) => {
        calls.push({ pattern, fn });
        return { stop: jest.fn(), start: jest.fn() };
      }
    };
  }

  function makeLoggerStub() {
    const infos = [];
    return {
      infos,
      info: (msg) => infos.push(msg),
      error: jest.fn(),
      warn: jest.fn()
    };
  }

  test('control cron not scheduled when disabled; planning/progress enabled', () => {
    jest.resetModules();
    const { scheduleCrons } = require('./utils/cronScheduler');

    const cron = makeCronStub();
    const logger = makeLoggerStub();
    const controller = { runControlLoop: jest.fn(), runPlanningLoop: jest.fn(), updateDailyProgress: jest.fn() };
    const services = {}; // not used
    const config = {
      control: { loopIntervalMinutes: 5 },
      cron: { control: false, planning: true, progress: true }
    };

    const { jobs, summary } = scheduleCrons({ cronLib: cron, logger }, controller, services, config);

    // Only 2 jobs scheduled for planning and progress
    expect(cron.calls.map(c => c.pattern)).toEqual(['0 6 * * *', '0 23 * * *']);
    expect(summary).toEqual({ control: 'disabled', planning: 'enabled', progress: 'enabled' });
    expect(logger.infos.some(s => String(s).includes('Cron jobs'))).toBe(true);
  });

  test('planning cron scheduled at 06:00 when enabled', () => {
    jest.resetModules();
    const { scheduleCrons } = require('./utils/cronScheduler');
    const cron = makeCronStub();
    const logger = makeLoggerStub();
    const controller = { runControlLoop: jest.fn(), runPlanningLoop: jest.fn(), updateDailyProgress: jest.fn() };
    const config = { control: { loopIntervalMinutes: 5 }, cron: { control: false, planning: true, progress: false } };

    scheduleCrons({ cronLib: cron, logger }, controller, {}, config);
    expect(cron.calls.find(c => c.pattern === '0 6 * * *')).toBeTruthy();
  });

  test('progress cron scheduled at 23:00 when enabled', () => {
    jest.resetModules();
    const { scheduleCrons } = require('./utils/cronScheduler');
    const cron = makeCronStub();
    const logger = makeLoggerStub();
    const controller = { runControlLoop: jest.fn(), runPlanningLoop: jest.fn(), updateDailyProgress: jest.fn() };
    const config = { control: { loopIntervalMinutes: 5 }, cron: { control: false, planning: false, progress: true } };

    scheduleCrons({ cronLib: cron, logger }, controller, {}, config);
    expect(cron.calls.find(c => c.pattern === '0 23 * * *')).toBeTruthy();
  });
});