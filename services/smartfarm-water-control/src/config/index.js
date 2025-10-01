require("dotenv").config();
const path = require("path");
const {
  loadSmartFarmPlots,
  mergePlotConfig,
  validatePlotMappings,
} = require("../utils/plotConfigLoader");

function loadConfiguration() {
  // Load plot geometries and areas from GeoJSON
  const geoJsonPath = path.join(
    __dirname,
    "../../data/smartfarm-plots.geojson",
  );
  const plotFeatures = loadSmartFarmPlots(geoJsonPath);

  // Build environment config map from PLOT_CONFIGS env variable
  // Format: plotId1:sensorId1:valveName1,plotId2:sensorId2:valveName2
  const plotConfigsEnv = process.env.PLOT_CONFIGS || "";
  const envConfig = {};

  if (plotConfigsEnv) {
    plotConfigsEnv.split(",").forEach((configStr) => {
      const [plotId, sensorId, valveName] = configStr
        .split(":")
        .map((s) => s.trim());

      if (plotId && sensorId && valveName) {
        envConfig[plotId] = { sensorId, valveName };
      }
    });
  }

  // Merge GeoJSON plots with environment configuration
  const plotConfigs = mergePlotConfig(plotFeatures, envConfig);
  validatePlotMappings(plotConfigs);

  // Build valve mapping from merged configs
  const valveMapping = new Map();
  plotConfigs.forEach((plot) => {
    valveMapping.set(plot.plotId, plot.valveName);
  });

  return {
    service: {
      port: parseInt(process.env.PORT || "3020"),
      environment: process.env.NODE_ENV || "development",
      logLevel: process.env.LOG_LEVEL || "info",
    },

    plots: plotConfigs,
    valveMapping,

    timescale: {
      host: process.env.TIMESCALE_HOST,
      port: parseInt(process.env.TIMESCALE_PORT || "5432"),
      database: process.env.TIMESCALE_DB,
      user: process.env.TIMESCALE_USER,
      password: process.env.TIMESCALE_PASSWORD,
      schemas: {
        planning: process.env.TIMESCALE_SCHEMA_PLANNING || "ros_gis_smartfarm",
        control:
          process.env.TIMESCALE_SCHEMA_CONTROL || "water_control_smartfarm",
      },
    },

    mssql: {
      host: process.env.MSSQL_HOST,
      port: parseInt(process.env.MSSQL_PORT || "1433"),
      database: process.env.MSSQL_DB,
      user: process.env.MSSQL_USER,
      password: process.env.MSSQL_PASSWORD,
      tableName: process.env.MSSQL_TABLE_VALVE_COMMAND || "tb_valve_command_v2",
    },

    ros: {
      apiUrl: process.env.ROS_API_URL,
      apiKey: process.env.ROS_API_KEY,
      endpoint:
        process.env.ROS_CALCULATION_ENDPOINT || "/calculate-water-demand",
    },

    control: {
      loopIntervalMinutes: parseInt(
        process.env.CONTROL_LOOP_INTERVAL_MINUTES || "5",
      ),
      planningIntervalHours: parseInt(
        process.env.PLANNING_INTERVAL_HOURS || "24",
      ),
      waterFlowRateLPM: parseInt(process.env.WATER_FLOW_RATE_LPM || "60"),

      moisture: {
        thresholdLowPercent: parseFloat(
          process.env.MOISTURE_THRESHOLD_LOW_PERCENT || "10",
        ),
        thresholdHighPercent: parseFloat(
          process.env.MOISTURE_THRESHOLD_HIGH_PERCENT || "15",
        ),
      },

      awd: {
        minWaterLevelCm: parseFloat(process.env.AWD_MIN_WATER_LEVEL_CM || "5"),
        maxWaterLevelCm: parseFloat(process.env.AWD_MAX_WATER_LEVEL_CM || "15"),
        dryingPeriodDays: parseInt(process.env.AWD_DRYING_PERIOD_DAYS || "7"),
      },
    },

    sensorData: {
      serviceUrl: process.env.SENSOR_DATA_SERVICE_URL,
      apiKey: process.env.SENSOR_DATA_API_KEY,
    },

    listener: {
      enabled: process.env.ENABLE_DB_LISTENER === "true",
      reconnectDelay: parseInt(
        process.env.LISTENER_RECONNECT_DELAY_MS || "5000",
      ),
      debounceWindow: parseInt(
        process.env.LISTENER_DEBOUNCE_WINDOW_MS || "5000",
      ),
    },
  };
}

// Validate configuration
function validateConfiguration(config) {
  const required = [
    "timescale.host",
    "timescale.database",
    "timescale.user",
    "mssql.host",
    "mssql.database",
    "mssql.user",
    "ros.apiUrl",
  ];

  for (const path of required) {
    const value = path.split(".").reduce((obj, key) => obj?.[key], config);
    if (!value) {
      throw new Error(`Missing required configuration: ${path}`);
    }
  }

  if (config.plots.length === 0) {
    throw new Error("No plots configured");
  }
}

const config = loadConfiguration();
validateConfiguration(config);

module.exports = config;
