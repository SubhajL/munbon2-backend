require("dotenv").config();

function loadConfiguration() {
  // Parse plot list
  const plots = process.env.SMART_FARM_PLOTS?.split(",") || [];

  // Build plot configurations
  const plotConfigs = plots.map((plotId) => {
    const sensorInfo = process.env[`${plotId}_SENSORS`];
    const valveName = process.env[`${plotId}_VALVE`];

    if (!sensorInfo || !valveName) {
      throw new Error(
        `Missing sensor or valve configuration for plot: ${plotId}`,
      );
    }

    const [sensorType, sensorId] = sensorInfo.split(":");

    return {
      plotId,
      areaRai: parseFloat(process.env.PLOT_AREA_RAI || "2.5"),
      controlMode: sensorType,
      sensorId,
      valveName,
      cropType: "rice", // Default crop type, can be extended
    };
  });

  // Build valve mapping
  const valveMapping = new Map();
  plots.forEach((plotId) => {
    const valveName = process.env[`${plotId}_VALVE`];
    if (valveName) {
      valveMapping.set(plotId, valveName);
    }
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
