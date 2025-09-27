const express = require("express");
const cron = require("node-cron");
const config = require("./config");
const logger = require("./utils/logger");

const { DatabaseConfig } = require("./config/database");
const { MoistureControlService } = require("./services/moistureControlService");
const { AWDControlService } = require("./services/awdControlService");
const { ValveCommandService } = require("./services/valveCommandService");
const { WaterPlanningService } = require("./services/waterPlanningService");
const { WaterBalanceService } = require("./services/waterBalanceService");
const { SensorClient } = require("./services/sensorClient");
const { WaterController } = require("./controllers/waterController");
const createRoutes = require("./routes");

class SmartFarmWaterControlApp {
  constructor() {
    this.app = express();
    this.db = new DatabaseConfig();
    this.services = {};
    this.controller = null;
    this.cronJobs = [];
  }

  async initialize() {
    try {
      logger.info("Initializing Smart Farm Water Control Service...");

      // Setup middleware
      this.app.use(express.json());
      this.app.use(express.urlencoded({ extended: true }));

      // Initialize databases
      const timescalePool = await this.db.initializeTimescaleDB(
        config.timescale,
      );
      const mssqlPool = await this.db.initializeMSSQL(config.mssql);

      // Initialize services
      this.services = {
        moistureControl: new MoistureControlService(config.control.moisture),
        awdControl: new AWDControlService(config.control.awd),
        valveCommand: new ValveCommandService({
          mssqlPool,
          timescalePool,
          valveMapping: config.valveMapping,
          tableName: config.mssql.tableName,
        }),
        waterPlanning: new WaterPlanningService({
          timescalePool,
          rosApiUrl: config.ros.apiUrl,
          rosApiKey: config.ros.apiKey,
          plotConfigs: config.plots,
        }),
        waterBalance: new WaterBalanceService({
          timescalePool,
          flowRateLPM: config.control.waterFlowRateLPM,
        }),
        sensorClient: new SensorClient(config.sensorData),
        config,
      };

      // Initialize controller
      this.controller = new WaterController(this.services);

      // Setup routes
      const routes = createRoutes(this.controller);
      this.app.use("/api", routes);

      // Setup cron jobs
      this.setupCronJobs();

      logger.info("Smart Farm Water Control Service initialized successfully");
    } catch (error) {
      logger.error({ error }, "Failed to initialize service");
      throw error;
    }
  }

  setupCronJobs() {
    // Control loop - runs every N minutes
    const controlInterval = `*/${config.control.loopIntervalMinutes} * * * *`;
    const controlJob = cron.schedule(controlInterval, async () => {
      try {
        logger.info("Running scheduled control loop");
        await this.controller.runControlLoop();
      } catch (error) {
        logger.error({ error }, "Control loop failed");
      }
    });
    this.cronJobs.push(controlJob);

    // Planning loop - runs daily at 6 AM
    const planningJob = cron.schedule("0 6 * * *", async () => {
      try {
        logger.info("Running scheduled planning loop");
        await this.controller.runPlanningLoop();
      } catch (error) {
        logger.error({ error }, "Planning loop failed");
      }
    });
    this.cronJobs.push(planningJob);

    // Daily progress update - runs daily at 11 PM
    const progressJob = cron.schedule("0 23 * * *", async () => {
      try {
        logger.info("Running scheduled progress update");
        await this.controller.updateDailyProgress();
      } catch (error) {
        logger.error({ error }, "Progress update failed");
      }
    });
    this.cronJobs.push(progressJob);

    logger.info("Cron jobs scheduled successfully");
  }

  async start() {
    await this.initialize();

    const port = config.service.port;
    this.server = this.app.listen(port, () => {
      logger.info({ port }, "Smart Farm Water Control Service started");
    });

    // Run initial planning on startup
    setTimeout(async () => {
      try {
        logger.info("Running initial planning loop");
        await this.controller.runPlanningLoop();
      } catch (error) {
        logger.error({ error }, "Initial planning loop failed");
      }
    }, 5000);
  }

  async shutdown() {
    logger.info("Shutting down Smart Farm Water Control Service...");

    // Stop cron jobs
    this.cronJobs.forEach((job) => job.stop());

    // Close server
    if (this.server) {
      await new Promise((resolve) => this.server.close(resolve));
    }

    // Close database connections
    await this.db.close();

    logger.info("Smart Farm Water Control Service shut down");
  }
}

// Handle process events
const app = new SmartFarmWaterControlApp();

process.on("SIGTERM", async () => {
  await app.shutdown();
  process.exit(0);
});

process.on("SIGINT", async () => {
  await app.shutdown();
  process.exit(0);
});

process.on("unhandledRejection", (reason, promise) => {
  logger.error({ reason, promise }, "Unhandled rejection");
});

process.on("uncaughtException", (error) => {
  logger.error({ error }, "Uncaught exception");
  process.exit(1);
});

// Start the application
app.start().catch((error) => {
  logger.error({ error }, "Failed to start application");
  process.exit(1);
});
