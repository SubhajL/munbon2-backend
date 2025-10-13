const express = require("express");
const cron = require("node-cron");
const config = require("./config");
const logger = require("./utils/logger");

const { DatabaseConfig } = require("./config/database");
const { TimescaleRepository } = require("./repository/timescaleRepository");
const { ControlModeService } = require("./services/controlModeService");
const { MoistureControlService } = require("./services/moistureControlService");
const { AWDControlService } = require("./services/awdControlService");
const { ValveCommandService } = require("./services/valveCommandService");
const { WaterPlanningService } = require("./services/waterPlanningService");
const { WaterBalanceService } = require("./services/waterBalanceService");
const { SensorDataService } = require("./services/sensorDataService");
const { SensorUpdateListener } = require("./services/sensorUpdateListener");
const { RealtimeControlService } = require("./services/realtimeControlService");
const { ValveAuditService } = require("./services/valveAuditService");
const { WaterController } = require("./controllers/waterController");
const createRoutes = require("./routes");

class SmartFarmWaterControlApp {
  constructor() {
    this.app = express();
    this.db = new DatabaseConfig();
    this.services = {};
    this.controller = null;
    this.listener = null;
    this.cronJobs = [];
    this.processingPlots = new Set();
  }

  async loadPlotConfigurationsFromDB(configRepository) {
    try {
      // Get plot configurations
      const plots = await configRepository.getAllPlotConfigurations();

      // Get sensor mappings
      const mappings = await configRepository.pool.query(`
        SELECT sensor_id, plot_id, sensor_type
        FROM ${config.configDb.schema}.sensor_plot_mapping
        WHERE plot_id NOT LIKE 'TEST-%'
        ORDER BY plot_id, sensor_type
      `);

      // Build plot config map
      const plotMap = new Map();
      plots.forEach(plot => {
        plotMap.set(plot.plotId, {
          plotId: plot.plotId,
          cropType: plot.cropType,
          controlMode: plot.controlMode,
          moistureSensorId: null,
          waterLevelSensorId: null,
          valveId: null
        });
      });

      // Add sensor mappings
      mappings.rows.forEach(row => {
        const plot = plotMap.get(row.plot_id);
        if (plot) {
          if (row.sensor_type === 'moisture') plot.moistureSensorId = row.sensor_id;
          if (row.sensor_type === 'water_level') plot.waterLevelSensorId = row.sensor_id;
          if (row.sensor_type === 'valve') plot.valveId = row.sensor_id;
        }
      });

      // Filter to plots with at least moisture sensor
      // Valve IDs will be derived from plot configuration or naming convention
      const configurePlots = Array.from(plotMap.values()).filter(
        p => p.moistureSensorId
      );

      // Auto-generate valve IDs if not mapped (using plot number from valve_states or convention)
      configurePlots.forEach(plot => {
        if (!plot.valveId) {
          // Derive valve name from plot position or use a default pattern
          // For now, use plot_id substring as valve identifier
          const plotShortId = plot.plotId.substring(0, 8);
          plot.valveId = `SV_${plotShortId}`;
        }
      });

      // Update config
      config.plots = configurePlots;

      // Build valve mapping
      const valveMapping = new Map();
      configurePlots.forEach(plot => {
        valveMapping.set(plot.plotId, plot.valveId);
      });
      config.valveMapping = valveMapping;

      logger.info(`Loaded ${configurePlots.length} plot configurations from database`);
      configurePlots.forEach(plot => {
        logger.info(`  - ${plot.plotId.substring(0,8)}... | ${plot.controlMode} | Valve: ${plot.valveId}`);
      });

      return configurePlots;
    } catch (error) {
      logger.error('Failed to load plot configurations from database');
      logger.error(error.message);
      logger.error(error.stack);
      throw error;
    }
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

      // MSSQL connection - make it optional for now
      let mssqlPool = null;
      try {
        mssqlPool = await this.db.initializeMSSQL(config.mssql);
      } catch (error) {
        logger.warn('MSSQL connection failed - valve commands will not work');
        logger.warn(error.message);
      }

      // Initialize config database connection (munbon_dev) - read-only, no schema creation
      const { Pool: PgPool } = require('pg');
      const configPool = new PgPool({
        host: config.configDb.host,
        port: config.configDb.port,
        database: config.configDb.database,
        user: config.configDb.user,
        password: config.configDb.password,
        max: 5,
        idleTimeoutMillis: 30000,
        connectionTimeoutMillis: 2000
      });

      // Test connection
      const testClient = await configPool.connect();
      await testClient.query('SELECT NOW()');
      testClient.release();
      logger.info('Configuration database (munbon_dev) connected successfully');

      // Initialize repositories
      const timescaleRepository = new TimescaleRepository(
        timescalePool,
        config.timescale.schemas,
      );

      const configRepository = new TimescaleRepository(
        configPool,
        { control: config.configDb.schema }
      );

      // Load plot configurations from database
      await this.loadPlotConfigurationsFromDB(configRepository);

      // Initialize control mode service and load modes
      const controlModeService = new ControlModeService(timescaleRepository);
      await controlModeService.loadModes();

      // Initialize services
      this.services = {
        timescaleRepository,
        controlMode: controlModeService,
        moistureControl: new MoistureControlService(config.control.moisture),
        awdControl: new AWDControlService(config.control.awd),
        valveCommand: new ValveCommandService({
          mssqlPool,
          timescaleRepository,
          valveMapping: config.valveMapping,
          tableName: config.mssql.tableName,
        }),
        waterPlanning: new WaterPlanningService({
          timescaleRepository,
          rosApiUrl: config.ros.apiUrl,
          rosApiKey: config.ros.apiKey,
          rosEndpoint: config.ros.endpoint,
          plotConfigs: config.plots,
        }),
        waterBalance: new WaterBalanceService({
          timescaleRepository,
          flowRateLPM: config.control.waterFlowRateLPM,
        }),
        sensorData: new SensorDataService({
          timescaleRepository,
        }),
        config,
      };

      this.services.valveAudit = new ValveAuditService(
        timescalePool,
        config.timescale.schemas.control,
      );

      // Initialize controller
      this.controller = new WaterController(this.services);

      // Setup routes
      const routes = createRoutes(this.controller);
      this.app.use("/api", routes);

      // Setup cron jobs
      this.setupCronJobs();

      // Setup sensor update listener if enabled
      if (config.listener.enabled) {
        await this.setupSensorListener(timescalePool);
      }

      logger.info("Smart Farm Water Control Service initialized successfully");
    } catch (error) {
      logger.error("Failed to initialize service");
      logger.error(error.message);
      logger.error(error.stack);
      throw error;
    }
  }

  async setupSensorListener(timescalePool) {
    try {
      const timescaleRepository = this.services.timescaleRepository;

      // Initialize realtime control service
      this.services.realtimeControl = new RealtimeControlService(
        timescaleRepository,
        this.services.valveCommand,
        logger,
        {
          moistureFreshnessWindowMs: config.listener.moistureFreshnessWindowMs,
        },
        this.services.valveAudit,
      );

      this.listener = new SensorUpdateListener(timescalePool, {
        reconnectDelay: config.listener.reconnectDelay,
        debounceWindow: config.listener.debounceWindow,
      });

      this.listener.on("sensor_reading", async (event) => {
        await this.services.realtimeControl.handleSensorReading(event);
      });

      this.listener.on("error", (error) => {
        logger.error({ error }, "Sensor update listener error");
      });

      await this.listener.start();

      logger.info(
        "Real-time control system enabled: sensor notifications will trigger immediate valve actions",
      );
    } catch (error) {
      logger.error({ error }, "Failed to setup sensor update listener");
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

    // Refresh control modes cache - runs every hour
    const controlModeRefreshJob = cron.schedule("0 * * * *", async () => {
      try {
        await this.services.controlMode.refreshIfStale();
      } catch (error) {
        logger.error({ error }, "Control mode cache refresh failed");
      }
    });
    this.cronJobs.push(controlModeRefreshJob);

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

    // Stop sensor listener
    if (this.listener) {
      await this.listener.stop();
    }

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
