"use strict";
/**
 * JobScheduler (F-08) — restores the cron scheduler that `src/index.js` requires.
 *
 * The original module was never committed, so `require('./jobs/job-scheduler')` threw
 * MODULE_NOT_FOUND and the service could not boot. This minimal, boot-safe singleton
 * registers the three documented schedules and delegates to the existing services.
 *
 * `node-cron`, the logger, and the domain services are required LAZILY (inside start /
 * the handlers) so that simply loading this module — and booting the service far enough
 * to fail on real infra (DB/Kafka) rather than a missing file — needs no extra deps.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.JobScheduler = void 0;

// Cron schedules. node-cron fires in the process TZ unless a timezone is passed; rid-ms sets
// no TZ (so container-local == UTC on EC2, ~7h off Bangkok), so pass the timezone explicitly.
const TIMEZONE = "Asia/Bangkok";
const CRON_OPTIONS = { timezone: TIMEZONE };
const DAILY_SHAPEFILE_CHECK = "0 6 * * *";      // 06:00 Asia/Bangkok daily
const DAILY_WATER_DEMAND_REFRESH = "0 7 * * *"; // 07:00 Asia/Bangkok daily
const WEEKLY_CLEANUP = "0 3 * * 0";             // 03:00 Asia/Bangkok Sundays

function log(level, msg, err) {
    try {
        const { logger } = require("../utils/logger");
        err ? logger[level](msg, err) : logger[level](msg);
    } catch (_) {
        // Logger unavailable (e.g. under a bare unit test) — degrade to console.
        (console[level] || console.log)(msg, err || "");
    }
}

class JobScheduler {
    constructor() {
        this.tasks = [];
        this.started = false;
    }

    static getInstance() {
        if (!JobScheduler.instance) {
            JobScheduler.instance = new JobScheduler();
        }
        return JobScheduler.instance;
    }

    async start() {
        if (this.started) {
            return;
        }
        const cron = require("node-cron");
        this.tasks.push(
            cron.schedule(
                DAILY_SHAPEFILE_CHECK,
                () => this._run("daily shapefile check", () => this._checkShapefiles()),
                CRON_OPTIONS
            )
        );
        this.tasks.push(
            cron.schedule(
                DAILY_WATER_DEMAND_REFRESH,
                () => this._run("water demand refresh", () => this._refreshWaterDemands()),
                CRON_OPTIONS
            )
        );
        this.tasks.push(
            cron.schedule(
                WEEKLY_CLEANUP,
                () => this._run("weekly cleanup", () => this._cleanupOldFiles()),
                CRON_OPTIONS
            )
        );
        this.started = true;
        log("info", `JobScheduler started (${this.tasks.length} cron jobs)`);
    }

    async stop() {
        for (const task of this.tasks) {
            try {
                task.stop();
            } catch (_) {
                // best-effort teardown
            }
        }
        this.tasks = [];
        this.started = false;
        log("info", "JobScheduler stopped");
    }

    async _run(name, fn) {
        log("info", `cron job start: ${name}`);
        try {
            await fn();
            log("info", `cron job done: ${name}`);
        } catch (err) {
            log("error", `cron job failed: ${name}`, err);
        }
    }

    async _refreshWaterDemands() {
        const { WaterDemandCalculatorService } = require("../services/water-demand-calculator.service");
        await WaterDemandCalculatorService.getInstance().updateAllWaterDemands();
    }

    async _cleanupOldFiles() {
        const { ShapeFileProcessorService } = require("../services/shapefile-processor.service");
        await ShapeFileProcessorService.getInstance().cleanupOldFiles();
    }

    async _checkShapefiles() {
        // Scaffold: the original daily ingest-source check was lost. Wire this to the
        // shapefile ingest source when it is available; logs until then.
        log("info", "daily shapefile check (scaffold — wire to ingest source)");
    }
}

exports.JobScheduler = JobScheduler;
