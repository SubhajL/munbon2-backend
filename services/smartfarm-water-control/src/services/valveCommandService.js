const sql = require('mssql');
const logger = require('../utils/logger');

class ValveCommandService {
  constructor(config) {
    this.mssqlPool = config.mssqlPool;
    this.timescaleRepository = config.timescaleRepository;
    this.valveMapping = config.valveMapping;
    this.tableName = config.tableName;
    this.valveStates = new Map();

    // SCADA valve name mapping: smartfarm -> SCADA
    this.scadaNameMapping = new Map([
      ['SV-U1', 'SV_C1_L'],
      ['SV-U2', 'SV_C1_R'],
      ['SV-U3', 'SV_C2_L'],
      ['SV-U4', 'SV_C2_R'],
      ['SV-U5', 'SV_C3_L'],
      ['SV-U6', 'SV_C3_R'],
      ['SV-U7', 'SV_C4_L'],
      ['SV-U8', 'SV_C4_R'],
      ['SV-L1', 'SV_L'],
      ['SV-L5', 'SV_M'],
      ['SV-L2', 'SV_N'],
      ['SV-L3', 'SV_O'],
      ['SV-L6', 'SV_P'],
      ['SV-L4', 'SV_Q']
    ]);
  }

  async sendValveCommand(plotId, level, timestamp, reason) {
    const smartfarmValveName = this.valveMapping.get(plotId);
    if (!smartfarmValveName) {
      throw new Error(`Valve not found for plot: ${plotId}`);
    }
    if (!this.mssqlPool) {
      throw new Error('MSSQL unavailable for valve commands');
    }

    // Translate smartfarm valve name to SCADA name
    const scadaValveName =
      this.scadaNameMapping.get(smartfarmValveName) || smartfarmValveName;

    try {
      const query = `
        INSERT INTO ${this.tableName}
        (valve_name, valve_level, startdatetime)
        VALUES (@valve_name, @valve_level, @startdatetime)
      `;

      await this.mssqlPool
        .request()
        .input('valve_name', sql.VarChar(50), scadaValveName)
        .input('valve_level', sql.Int, level)
        .input('startdatetime', sql.DateTime, timestamp)
        .query(query);

      logger.info(
        {
          plotId,
          smartfarmValveName,
          scadaValveName,
          level,
          reason,
          timestamp: timestamp.toISOString()
        },
        'Valve command sent to MSSQL'
      );

      // Update local state tracking
      await this.updateValveStatus(
        plotId,
        level === 1 ? 'ON' : 'OFF',
        timestamp
      );

      return {
        success: true,
        smartfarmValveName,
        scadaValveName,
        level,
        timestamp
      };
    } catch (error) {
      logger.error({ error, plotId, level }, 'Failed to send valve command');
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
      lastChanged: timestamp
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
      cycle.flowRate
    );

    try {
      await this.timescaleRepository.recordIrrigationCycle({
        ...cycle,
        valveName,
        volumeLiters,
        controlMode: cycle.controlMode || 'UNKNOWN'
      });

      logger.info(
        {
          plotId: cycle.plotId,
          volumeLiters,
          duration: (cycle.endTime - cycle.startTime) / 1000 / 60
        },
        'Irrigation cycle recorded'
      );
    } catch (error) {
      logger.error({ error, cycle }, 'Failed to record irrigation cycle');
      throw error;
    }
  }

  async getValveStatus(plotId) {
    const valveName = this.valveMapping.get(plotId);
    const state = this.valveStates.get(plotId) || { status: 'UNKNOWN' };

    return {
      plotId,
      valveName: valveName || 'UNKNOWN',
      status: state.status,
      lastChanged: state.lastChanged
    };
  }

  formatDateForMSSQL(date) {
    // Format date for MSSQL: YYYY-MM-DD HH:MM:SS
    const pad = (num) => String(num).padStart(2, '0');

    return (
      `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ` +
      `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
    );
  }

  sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  recordValveMetric(plotId, attempt, success, error = null) {
    const logData = {
      plotId,
      attempt,
      success
    };

    if (error) {
      logData.error = error;
    }

    if (success) {
      logger.info(logData, 'Valve command metric: success');
    } else {
      logger.warn(logData, 'Valve command metric: failure');
    }
  }

  async sendValveCommandWithRetry(
    plotId,
    level,
    timestamp,
    reason,
    maxRetries = 3
  ) {
    let lastError;

    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      try {
        const result = await this.sendValveCommand(
          plotId,
          level,
          timestamp,
          reason
        );

        this.recordValveMetric(plotId, attempt, true, null);
        return result;
      } catch (error) {
        lastError = error;

        this.recordValveMetric(plotId, attempt, false, error.message);

        if (attempt < maxRetries) {
          const delayMs = Math.pow(2, attempt - 1) * 1000;
          logger.warn(
            { plotId, attempt, delayMs, error: error.message },
            'Valve command failed, retrying...'
          );
          await this.sleep(delayMs);
        }
      }
    }

    logger.error(
      { plotId, maxRetries, error: lastError.message },
      'Valve command failed after all retries'
    );
    throw lastError;
  }
}

module.exports = { ValveCommandService };
