require('dotenv').config();
const path = require('path');
const fs = require('fs');
const {
  loadSmartFarmPlots,
  mergePlotConfig,
  validatePlotMappings
} = require('../utils/plotConfigLoader');

function tryLoadDeviceMapping() {
  try {
    const mappingPath = path.resolve(__dirname, '../../config/device-mapping.json');
    if (!fs.existsSync(mappingPath)) return null;
    const raw = fs.readFileSync(mappingPath, 'utf8');
    const json = JSON.parse(raw);

    // Build convenient lookup by plotId
    const byPlotId = new Map();
    if (json.plot_device_mapping) {
      for (const [plotId, entry] of Object.entries(json.plot_device_mapping)) {
        byPlotId.set(plotId, {
          plotName: entry.plot_name,
          controlMode: entry.control_mode,
          solenoidValve: entry.devices?.solenoid_valve || null,
          flowMeter: entry.devices?.flow_meter || null,
          moistureSensor: entry.devices?.moisture_sensor || null,
        });
      }
    }

    return {
      meta: {
        version: json.version || null,
        description: json.description || null,
        last_updated: json.last_updated || null,
      },
      byPlotId,
    };
  } catch (e) {
    // Fail-soft; continue without mapping
    return null;
  }
}

function loadConfiguration() {
  // Plot configurations will be loaded from database at runtime
  // No longer using PLOT_CONFIGS env variable or GeoJSON
  // Plot configs are in munbon_dev.water_control_smartfarm.plot_configurations
  // Sensor mappings are in munbon_dev.water_control_smartfarm.sensor_plot_mapping

  const deviceNames = process.env.USE_DEVICE_MAPPING_JSON === 'true' ? tryLoadDeviceMapping() : null;

  return {
    service: {
      port: parseInt(process.env.PORT || '3020'),
      environment: process.env.NODE_ENV || 'development',
      logLevel: process.env.LOG_LEVEL || 'info'
    },

    deviceNames,

    // Plot configs will be populated at runtime from database
    plots: [],
    valveMapping: new Map(),

    // Configuration database connection (munbon_dev)
    configDb: {
      host: process.env.CONFIG_DB_HOST || process.env.TIMESCALE_HOST,
      port: parseInt(process.env.CONFIG_DB_PORT || process.env.TIMESCALE_PORT || '5432'),
      database: process.env.CONFIG_DB_NAME || 'munbon_dev',
      user: process.env.CONFIG_DB_USER || process.env.TIMESCALE_USER,
      password: process.env.CONFIG_DB_PASSWORD || process.env.TIMESCALE_PASSWORD,
      schema: process.env.CONFIG_DB_SCHEMA || 'water_control_smartfarm'
    },

    timescale: {
      host: process.env.TIMESCALE_HOST,
      port: parseInt(process.env.TIMESCALE_PORT || '5432'),
      database: process.env.TIMESCALE_DB,
      user: process.env.TIMESCALE_USER,
      password: process.env.TIMESCALE_PASSWORD,
      schemas: {
        planning: process.env.TIMESCALE_SCHEMA_PLANNING || 'ros_gis_smartfarm',
        control:
          process.env.TIMESCALE_SCHEMA_CONTROL || 'water_control_smartfarm'
      }
    },

    mssql: {
      host: process.env.MSSQL_HOST,
      port: parseInt(process.env.MSSQL_PORT || '1433'),
      database: process.env.MSSQL_DB,
      user: process.env.MSSQL_USER,
      password: process.env.MSSQL_PASSWORD,
      tableName: process.env.MSSQL_TABLE_VALVE_COMMAND || 'tb_valve_command_v2'
    },

    waterPlanning: {
      serviceUrl: process.env.WATER_PLANNING_SERVICE_URL || 'http://localhost:4002',
      apiKey: process.env.WATER_PLANNING_API_KEY,
      endpoint: process.env.WATER_PLANNING_ENDPOINT || '/api/v1/water-demand/calculate',
      timeout: parseInt(process.env.WATER_PLANNING_TIMEOUT_MS || '10000')
    },

    control: {
      loopIntervalMinutes: parseInt(
        process.env.CONTROL_LOOP_INTERVAL_MINUTES || '5'
      ),
      planningIntervalHours: parseInt(
        process.env.PLANNING_INTERVAL_HOURS || '24'
      ),
      waterFlowRateLPM: parseInt(process.env.WATER_FLOW_RATE_LPM || '60'),

      moisture: {
        thresholdLowPercent: parseFloat(
          process.env.MOISTURE_THRESHOLD_LOW_PERCENT || '50'
        ),
        thresholdHighPercent: parseFloat(
          process.env.MOISTURE_THRESHOLD_HIGH_PERCENT || '69'
        )
      },

      awd: {
        minWaterLevelCm: parseFloat(
          process.env.AWD_MIN_WATER_LEVEL_CM || '-10'
        ),
        maxWaterLevelCm: parseFloat(process.env.AWD_MAX_WATER_LEVEL_CM || '10'),
        dryingPeriodDays: parseInt(process.env.AWD_DRYING_PERIOD_DAYS || '7')
      }
    },

    sensorData: {
      serviceUrl: process.env.SENSOR_DATA_SERVICE_URL,
      apiKey: process.env.SENSOR_DATA_API_KEY
    },

    listener: {
      enabled: process.env.ENABLE_DB_LISTENER === 'true',
      reconnectDelay: parseInt(
        process.env.LISTENER_RECONNECT_DELAY_MS || '5000'
      ),
      debounceWindow: parseInt(
        process.env.LISTENER_DEBOUNCE_WINDOW_MS || '5000'
      ),
      moistureFreshnessWindowMs: parseInt(
        process.env.MOISTURE_FRESHNESS_WINDOW_MS || '300000'
      )
    }
  };
}

// Validate configuration
function validateConfiguration(config) {
  const required = [
    'timescale.host',
    'timescale.database',
    'timescale.user',
    'configDb.host',
    'configDb.database',
    'configDb.user',
    'mssql.host',
    'mssql.database',
    'mssql.user',
    'waterPlanning.serviceUrl'
  ];

  for (const path of required) {
    const value = path.split('.').reduce((obj, key) => obj?.[key], config);
    if (!value) {
      throw new Error(`Missing required configuration: ${path}`);
    }
  }

  // Plot validation removed - plots are loaded from database at runtime
}

const config = loadConfiguration();
validateConfiguration(config);

module.exports = config;
