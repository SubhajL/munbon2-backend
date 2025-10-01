const sql = require("mssql");
const logger = require("../utils/logger");

class ValveCommandService {
  constructor(config) {
    this.mssqlPool = config.mssqlPool;
    this.timescaleRepository = config.timescaleRepository;
    this.valveMapping = config.valveMapping;
    this.tableName = config.tableName;
    this.valveStates = new Map();
  }

  async sendValveCommand(plotId, level, timestamp, reason) {
    const valveName = this.valveMapping.get(plotId);
    if (!valveName) {
      throw new Error(`Valve not found for plot: ${plotId}`);
    }

    try {
      const query = `
        INSERT INTO ${this.tableName}
        (valve_name, valve_level, startdatetime)
        VALUES (@valve_name, @valve_level, @startdatetime)
      `;

      await this.mssqlPool
        .request()
        .input("valve_name", sql.VarChar(50), valveName)
        .input("valve_level", sql.Int, level)
        .input("startdatetime", sql.DateTime, timestamp)
        .query(query);

      logger.info(
        {
          plotId,
          valveName,
          level,
          reason,
          timestamp: timestamp.toISOString(),
        },
        "Valve command sent to MSSQL",
      );

      // Update local state tracking
      await this.updateValveStatus(
        plotId,
        level === 1 ? "ON" : "OFF",
        timestamp,
      );

      return {
        success: true,
        valveName,
        level,
        timestamp,
      };
    } catch (error) {
      logger.error({ error, plotId, level }, "Failed to send valve command");
      throw error;
    }
  }

  async updateValveStatus(plotId, status, timestamp) {
    const valveName = this.valveMapping.get(plotId);
    if (!valveName) {
      return;
    }

    // Update local state
    this.valveStates.set(plotId, {
      status,
      valveName,
      lastChanged: timestamp,
    });

    // Store in TimescaleDB
    await this.timescaleRepository.updateValveStatus(
      plotId,
      valveName,
      status,
      timestamp
    );
  }

  calculateWaterUsage(onTime, offTime, flowRateLPM) {
    if (offTime <= onTime) {
      return 0;
    }

    const durationMinutes = (offTime - onTime) / (1000 * 60);
    return Math.round(durationMinutes * flowRateLPM);
  }

  async recordIrrigationCycle(cycle) {
    const valveName = this.valveMapping.get(cycle.plotId);
    if (!valveName) {
      return;
    }

    const volumeLiters = this.calculateWaterUsage(
      cycle.startTime,
      cycle.endTime,
      cycle.flowRate,
    );

    try {
      await this.timescaleRepository.recordIrrigationCycle({
        ...cycle,
        valveName,
        volumeLiters,
        controlMode: cycle.controlMode || "UNKNOWN",
      });

      logger.info(
        {
          plotId: cycle.plotId,
          volumeLiters,
          duration: (cycle.endTime - cycle.startTime) / 1000 / 60,
        },
        "Irrigation cycle recorded",
      );
    } catch (error) {
      logger.error({ error, cycle }, "Failed to record irrigation cycle");
      throw error;
    }
  }

  async getValveStatus(plotId) {
    const valveName = this.valveMapping.get(plotId);
    const state = this.valveStates.get(plotId) || { status: "UNKNOWN" };

    return {
      plotId,
      valveName: valveName || "UNKNOWN",
      status: state.status,
      lastChanged: state.lastChanged,
    };
  }

  formatDateForMSSQL(date) {
    // Format date for MSSQL: YYYY-MM-DD HH:MM:SS
    const pad = (num) => String(num).padStart(2, "0");

    return (
      `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ` +
      `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
    );
  }
}

module.exports = { ValveCommandService };
