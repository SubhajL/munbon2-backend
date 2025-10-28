const express = require('express');
const cron = require('node-cron');
const { scheduleCrons } = require('./utils/cronScheduler');
const config = require('./config');
const logger = require('./utils/logger');

const { DatabaseConfig } = require('./config/database');
const { TimescaleRepository } = require('./repository/timescaleRepository');
const { ControlModeService } = require('./services/controlModeService');
const { MoistureControlService } = require('./services/moistureControlService');
const { AWDControlService } = require('./services/awdControlService');
const { ValveCommandService } = require('./services/valveCommandService');
const { WaterPlanningService } = require('./services/waterPlanningService');
const { WaterBalanceService } = require('./services/waterBalanceService');
const { SensorDataService } = require('./services/sensorDataService');
const { SensorUpdateListener } = require('./services/sensorUpdateListener');
const { RealtimeControlService } = require('./services/realtimeControlService');
const { ValveAuditService } = require('./services/valveAuditService');
const OutboxPoller = require('./services/outboxPoller');
const OutboxCleanupService = require('./services/outboxCleanupService');
const GeoSpatialSensorResolver = require('./services/geoSpatialSensorResolver');
const { WaterController } = require('./controllers/waterController');
const createRoutes = require('./routes');
const { buildValveMappingFromDb, mergeValveMapping } = require('./utils/plotConfigBuilder');

class SmartFarmWaterControlApp {
  constructor() {
    this.app = express();
    this.db = new DatabaseConfig();
    this.services = {};
    this.controller = null;
    this.listener = null;
    this.outboxPoller = null;
    this.outboxCleanup = null;
    this.cronJobs = [];
    this.processingPlots = new Set();
  }

  async loadPlotConfigurationsFromDB(configRepository) {
    try {
      const {
        buildPlotConfigsFromEnriched
      } = require('./utils/plotConfigBuilder');

      // Read from enriched views
      const plots = await configRepository.getEnrichedPlotConfigurations(
        configRepository.pool
      );
      const mappings = await configRepository.getEnrichedSensorMappings(
        configRepository.pool
      );

      const base = buildPlotConfigsFromEnriched({
        plots,
        mappings,
        deviceOverrides: null
      });

      // Load valve mapping strictly from DB
      const dbValveMap = await buildValveMappingFromDb(configRepository);
      const merged = mergeValveMapping({ plots: base.plots, dbValveMap });

      // Update runtime config
      config.plots = merged.plots;
      config.valveMapping = merged.valveMapping;

      logger.info(
        `Loaded ${merged.plots.length} plot configurations from database`
      );
      merged.plots.forEach((plot) => {
        logger.info(
          `  - ${plot.plotId.substring(0, 8)}... | ${plot.controlMode} | Valve: ${plot.valveId}`
        );
      });

      return merged.plots;
    } catch (error) {
      logger.error('Failed to load plot configurations from database');
      logger.error(error.message);
      logger.error(error.stack);
      throw error;
    }
  }

  async initialize() {
    try {
      logger.info('Initializing Smart Farm Water Control Service...');

      // Setup middleware
      this.app.use(express.json());
      this.app.use(express.urlencoded({ extended: true }));

      // Initialize databases
      const timescalePool = await this.db.initializeTimescaleDB(
        config.timescale
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
        max: 2,
        idleTimeoutMillis: 30000,
        connectionTimeoutMillis: 5000
      });

      // Test connection
      const testClient = await configPool.connect();
      await testClient.query('SELECT NOW()');
      testClient.release();
      logger.info('Configuration database (munbon_dev) connected successfully');

      // Initialize repositories
      const timescaleRepository = new TimescaleRepository(
        timescalePool,
        config.timescale.schemas
      );

      const configRepository = new TimescaleRepository(configPool, {
        control: config.configDb.schema,
        planning: 'ros_gis_smartfarm'
      });

      // Load plot configurations from database
      await this.loadPlotConfigurationsFromDB(configRepository);

      // Initialize control mode service and load modes
      const controlModeService = new ControlModeService(timescaleRepository);
      await controlModeService.loadModes();

      // Initialize services
      this.services = {
        timescaleRepository,
        configRepository, // expose config repo for other services
        controlMode: controlModeService,
        moistureControl: new MoistureControlService(config.control.moisture),
        awdControl: new AWDControlService(config.control.awd),
        valveCommand: new ValveCommandService({
          mssqlPool,
          timescaleRepository,
          valveMapping: config.valveMapping,
          tableName: config.mssql.tableName,
          timezone: config.mssql.timezone
        }),
        waterPlanning: new WaterPlanningService({
          planningRepository: configRepository, // write planned data to munbon_dev
          configRepository,
          waterPlanningUrl: config.waterPlanning.serviceUrl,
          waterPlanningApiKey: config.waterPlanning.apiKey,
          waterPlanningEndpoint: config.waterPlanning.endpoint,
          timeout: config.waterPlanning.timeout,
          plotConfigs: config.plots,
          mode: config.waterPlanning.mode
        }),
        waterBalance: new WaterBalanceService({
          timescaleRepository,
          flowRateLPM: config.control.waterFlowRateLPM
        }),
        sensorData: new SensorDataService({
          timescaleRepository
        }),
        config
      };

      this.services.valveAudit = new ValveAuditService(
        timescalePool,
        config.timescale.schemas.control
      );

      // Initialize geo-spatial sensor resolver for water level sensors
      this.services.geoSpatialResolver = new GeoSpatialSensorResolver({
        repository: configRepository,
        logger,
        enableAutoMapping: true
      });

      // Initialize controller
      this.controller = new WaterController(this.services);

      // Serve static files for health dashboard
      this.app.use(express.static('public'));

      // Setup routes
      const routes = createRoutes(this.controller, this.services);
      this.app.use('/api', routes);

      // Setup cron jobs
      this.setupCronJobs();

      // Setup sensor update listener if enabled
      if (config.listener.enabled) {
        await this.setupSensorListener();
      }

      // Setup outbox poller if enabled
      // Note: Outbox table is in sensor_data (timescalePool) where triggers write
      if (config.outbox.enabled) {
        await this.setupOutboxPoller(timescalePool, timescaleRepository);
      }

      // Setup outbox cleanup if enabled
      if (config.outbox.cleanup.enabled) {
        await this.setupOutboxCleanup(timescalePool, timescaleRepository);
      }

      logger.info('Smart Farm Water Control Service initialized successfully');
    } catch (error) {
      logger.error('Failed to initialize service');
      logger.error(error.message);
      logger.error(error.stack);
      throw error;
    }
  }

  async setupSensorListener() {
    try {
      const timescaleRepository = this.services.timescaleRepository;

      // Initialize realtime control service
      this.services.realtimeControl = new RealtimeControlService(
        timescaleRepository,
        this.services.valveCommand,
        logger,
        {
          moistureFreshnessWindowMs: config.listener.moistureFreshnessWindowMs,
          readingsRepository: this.services.configRepository,
          geoSpatialResolver: this.services.geoSpatialResolver
        },
        this.services.valveAudit
      );

      // Pass connection config, not pool object
      const listenerConfig = {
        host: config.timescale.host,
        port: config.timescale.port,
        database: config.timescale.database,
        user: config.timescale.user,
        password: config.timescale.password
      };

      this.listener = new SensorUpdateListener(listenerConfig, {
        reconnectDelay: config.listener.reconnectDelay,
        debounceWindow: config.listener.debounceWindow
      });

      this.listener.on('sensor_reading', async (event) => {
        await this.services.realtimeControl.handleSensorReading(event);
      });

      this.listener.on('error', (error) => {
        logger.error({ error }, 'Sensor update listener error');
      });

      await this.listener.start();

      logger.info(
        'Real-time control system enabled: sensor notifications will trigger immediate valve actions'
      );
    } catch (error) {
      logger.error({ error }, 'Failed to setup sensor update listener');
      throw error;
    }
  }

  async setupOutboxPoller(pool, repository) {
    try {
      // Ensure realtimeControl service is initialized
      if (!this.services.realtimeControl) {
        const timescaleRepository = this.services.timescaleRepository;
        this.services.realtimeControl = new RealtimeControlService(
          timescaleRepository,
          this.services.valveCommand,
          logger,
          {
            moistureFreshnessWindowMs:
              config.listener.moistureFreshnessWindowMs,
            readingsRepository: this.services.configRepository,
            geoSpatialResolver: this.services.geoSpatialResolver
          },
          this.services.valveAudit
        );
      }

      this.outboxPoller = new OutboxPoller({
        repository: repository,
        realtimeControlService: this.services.realtimeControl,
        pollIntervalMs: config.outbox.pollIntervalMs,
        batchSize: config.outbox.batchSize,
        logger,
        pool: pool
      });

      this.outboxPoller.start();

      logger.info(
        {
          pollIntervalMs: config.outbox.pollIntervalMs,
          batchSize: config.outbox.batchSize
        },
        'Outbox poller enabled for durable sensor notification processing'
      );
    } catch (error) {
      logger.error({ error }, 'Failed to setup outbox poller');
      throw error;
    }
  }

  async setupOutboxCleanup(pool, repository) {
    try {
      this.outboxCleanup = new OutboxCleanupService({
        repository: repository,
        retentionDays: config.outbox.cleanup.retentionDays,
        cleanupIntervalHours: config.outbox.cleanup.cleanupIntervalHours,
        logger,
        pool: pool
      });

      this.outboxCleanup.start();

      logger.info(
        {
          retentionDays: config.outbox.cleanup.retentionDays,
          cleanupIntervalHours: config.outbox.cleanup.cleanupIntervalHours
        },
        'Outbox cleanup service enabled'
      );
    } catch (error) {
      logger.error({ error }, 'Failed to setup outbox cleanup');
      throw error;
    }
  }

  setupCronJobs() {
    // Schedule app crons per flags (control/planning/progress)
    const { jobs } = scheduleCrons(
      { cronLib: cron, logger },
      this.controller,
      this.services,
      config
    );

    // Track created jobs
    for (const key of Object.keys(jobs)) {
      if (jobs[key]) this.cronJobs.push(jobs[key]);
    }

    // Refresh control modes cache - runs every hour (independent of cron flags)
    const controlModeRefreshJob = cron.schedule('0 * * * *', async () => {
      try {
        await this.services.controlMode.refreshIfStale();
      } catch (error) {
        logger.error({ error }, 'Control mode cache refresh failed');
      }
    });
    this.cronJobs.push(controlModeRefreshJob);

    logger.info('Cron jobs scheduled successfully');
  }

  async start() {
    await this.initialize();

    const port = config.service.port;
    this.server = this.app.listen(port, () => {
      logger.info({ port }, 'Smart Farm Water Control Service started');
    });

    // Run initial planning on startup
    setTimeout(async () => {
      try {
        logger.info('Running initial planning loop');
        await this.controller.runPlanningLoop();
      } catch (error) {
        logger.error({ error }, 'Initial planning loop failed');
      }
    }, 5000);
  }

  async shutdown() {
    logger.info('Shutting down Smart Farm Water Control Service...');

    // Stop sensor listener
    if (this.listener) {
      await this.listener.stop();
    }

    // Stop outbox poller
    if (this.outboxPoller) {
      this.outboxPoller.stop();
    }

    // Stop outbox cleanup
    if (this.outboxCleanup) {
      this.outboxCleanup.stop();
    }

    // Stop cron jobs
    this.cronJobs.forEach((job) => job.stop());

    // Close server
    if (this.server) {
      await new Promise((resolve) => this.server.close(resolve));
    }

    // Close database connections
    await this.db.close();

    logger.info('Smart Farm Water Control Service shut down');
  }
}

// Handle process events
const app = new SmartFarmWaterControlApp();

process.on('SIGTERM', async () => {
  await app.shutdown();
  process.exit(0);
});

process.on('SIGINT', async () => {
  await app.shutdown();
  process.exit(0);
});

process.on('unhandledRejection', (reason, promise) => {
  logger.error({ reason, promise }, 'Unhandled rejection');
});

process.on('uncaughtException', (error) => {
  logger.error({ error }, 'Uncaught exception');
  process.exit(1);
});

// Start the application
app.start().catch((error) => {
  logger.error({ error }, 'Failed to start application');
  process.exit(1);
});
