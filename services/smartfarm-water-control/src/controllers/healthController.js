const { exec } = require('child_process');
const { promisify } = require('util');
const logger = require('../utils/logger');

const execAsync = promisify(exec);

class HealthController {
  constructor(services) {
    this.repository = services.timescaleRepository;
    this.configRepository = services.configRepository;
  }

  async checkHealth(req, res) {
    try {
      const health = {
        status: 'healthy',
        timestamp: new Date().toISOString(),
        app: {
          uptime: process.uptime(),
          memory: process.memoryUsage(),
          pid: process.pid
        },
        workers: await this.checkWorkers(),
        database: await this.checkDatabase()
      };

      res.json(health);
    } catch (error) {
      logger.error({ error }, 'Health check failed');
      res.status(500).json({
        status: 'unhealthy',
        error: error.message
      });
    }
  }

  async checkWorkers() {
    try {
      const { stdout } = await execAsync(
        'ps aux | grep -E "(start-zip-watcher|run-waterlevel-listener)" | grep -v grep'
      );

      const lines = stdout
        .trim()
        .split('\n')
        .filter((l) => l);
      const zipWatcher = lines.find((l) => l.includes('start-zip-watcher'));
      const waterLevelListener = lines.find((l) =>
        l.includes('run-waterlevel-listener')
      );

      return {
        zipWatcher: {
          running: !!zipWatcher,
          pid: zipWatcher ? parseInt(zipWatcher.trim().split(/\s+/)[1]) : null
        },
        waterLevelListener: {
          running: !!waterLevelListener,
          pid: waterLevelListener
            ? parseInt(waterLevelListener.trim().split(/\s+/)[1])
            : null
        }
      };
    } catch (error) {
      return {
        zipWatcher: { running: false, error: error.message },
        waterLevelListener: { running: false, error: error.message }
      };
    }
  }

  async checkDatabase() {
    try {
      const result = await this.repository.pool.query('SELECT NOW()');
      return {
        connected: true,
        timestamp: result.rows[0].now
      };
    } catch (error) {
      return {
        connected: false,
        error: error.message
      };
    }
  }

  async getSensorData(req, res) {
    try {
      const { date, sensorType } = req.query;

      if (!date || !sensorType) {
        return res.status(400).json({
          error: 'Missing required parameters: date, sensorType'
        });
      }

      if (!['moisture', 'water_level'].includes(sensorType)) {
        return res.status(400).json({
          error: 'Invalid sensorType. Must be moisture or water_level'
        });
      }

      const targetDate = new Date(date);
      const nextDate = new Date(targetDate);
      nextDate.setDate(nextDate.getDate() + 1);

      const tableName =
        sensorType === 'moisture'
          ? 'moisture_readings'
          : 'water_level_readings';
      const valueColumn =
        sensorType === 'moisture' ? 'moisture_surface_pct' : 'level_cm';

      const query = `
        SELECT 
          sensor_id,
          time,
          ${valueColumn} as value,
          location_lat as lat,
          location_lng as lng
        FROM public.${tableName}
        WHERE time >= $1 AND time < $2
        ORDER BY time ASC
      `;

      const result = await this.repository.pool.query(query, [
        targetDate,
        nextDate
      ]);

      res.json({
        date: date,
        sensorType: sensorType,
        count: result.rows.length,
        data: result.rows
      });
    } catch (error) {
      logger.error({ error }, 'Failed to fetch sensor data');
      res.status(500).json({
        error: error.message
      });
    }
  }
}

module.exports = { HealthController };
