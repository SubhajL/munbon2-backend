const DEFAULT_PLANNING_CRON = '0 6 * * *';
const DEFAULT_PROGRESS_CRON = '0 23 * * *';

/**
 * Schedule cron jobs based on enablement flags.
 * @param {{ cronLib: { schedule: Function }, logger: { info: Function, error?: Function, warn?: Function } }} io
 * @param {{ runControlLoop: Function, runPlanningLoop: Function, updateDailyProgress: Function }} controller
 * @param {any} services - not used currently, reserved for future
 * @param {{ control: { loopIntervalMinutes: number }, cron: { control: boolean, planning: boolean, progress: boolean } }} config
 * @returns {{ jobs: Record<string, any>, summary: { control: string, planning: string, progress: string } }}
 */
function scheduleCrons(io, controller, _services, config) {
  const jobs = {};
  const summary = {
    control: config.cron.control ? 'enabled' : 'disabled',
    planning: config.cron.planning ? 'enabled' : 'disabled',
    progress: config.cron.progress ? 'enabled' : 'disabled'
  };

  // Control loop (gated)
  if (config.cron.control) {
    const interval = Number(config.control.loopIntervalMinutes || 5);
    const pattern = `*/${interval} * * * *`;
    jobs.controlJob = io.cronLib.schedule(pattern, async () => {
      try {
        io.logger.info('Running scheduled control loop');
        await controller.runControlLoop();
      } catch (error) {
        io.logger.error && io.logger.error({ error }, 'Control loop failed');
      }
    });
  }

  // Planning loop (daily at 06:00)
  if (config.cron.planning) {
    jobs.planningJob = io.cronLib.schedule(DEFAULT_PLANNING_CRON, async () => {
      try {
        io.logger.info('[CRON] 💓 Planning heartbeat (06:00)');
        io.logger.info('Running scheduled planning loop');
        await controller.runPlanningLoop();
      } catch (error) {
        io.logger.error && io.logger.error({ error }, 'Planning loop failed');
      }
    });
  }

  // Daily progress update (daily at 23:00)
  if (config.cron.progress) {
    jobs.progressJob = io.cronLib.schedule(DEFAULT_PROGRESS_CRON, async () => {
      try {
        io.logger.info('[CRON] 💓 Progress heartbeat (23:00)');
        io.logger.info('Running scheduled progress update');
        await controller.updateDailyProgress();
      } catch (error) {
        io.logger.error && io.logger.error({ error }, 'Progress update failed');
      }
    });
  }

  io.logger.info(
    `Cron jobs scheduled: control=${summary.control}, planning=${summary.planning}, progress=${summary.progress}`
  );

  return { jobs, summary };
}

module.exports = { scheduleCrons, DEFAULT_PLANNING_CRON, DEFAULT_PROGRESS_CRON };