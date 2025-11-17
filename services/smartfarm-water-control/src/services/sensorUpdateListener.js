const { EventEmitter } = require('events');
const { Client } = require('pg');
const logger = require('../utils/logger');

class SensorUpdateListener extends EventEmitter {
  constructor(connectionConfig, config = {}) {
    super();
    this.connectionConfig = connectionConfig;
    this.client = null;
    this.isConnected = false;
    this.isStopped = false;
    this.reconnectDelay = config.reconnectDelay || 5000;
    this.debounceWindow = config.debounceWindow || 5000;
    this.heartbeatInterval = config.heartbeatInterval || 30000;
    this.recentNotifications = new Map();
    this.debounceTimeouts = new Map();
    this.heartbeatTimer = null;
  }

  async start() {
    if (this.isConnected) {
      return;
    }

    try {
      this.client = new Client({
        ...this.connectionConfig,
        keepAlive: true,
        statement_timeout: 0,
        query_timeout: 0,
        application_name: 'smartfarm-water-control-listener'
      });

      await this.client.connect();
      this.isConnected = true;
      this.isStopped = false;

      // Clear stale debounce entries on reconnect
      this.clearDebounceMap();

      // Set session timeouts to 0 to prevent server-side disconnection
      await this.client.query('SET idle_session_timeout = 0');
      await this.client.query('SET idle_in_transaction_session_timeout = 0');

      await this.client.query('LISTEN sensor_evaluation_needed');

      this.client.on('notification', this.handleNotification.bind(this));
      this.client.on('error', this.handleError.bind(this));

      // Start heartbeat to detect silent disconnections
      this.startHeartbeat();

      logger.info(
        'Sensor update listener started (dedicated connection)'
      );
    } catch (error) {
      logger.error({ error }, 'Failed to start sensor update listener');
      this.isConnected = false;
      this.cleanupClient();
      throw error;
    }
  }

  handleNotification(msg) {
    if (msg.channel !== 'sensor_evaluation_needed') {
      return;
    }

    try {
      const payload = JSON.parse(msg.payload);

      if (!this.validatePayload(payload)) {
        logger.warn({ payload }, 'Invalid notification payload');
        return;
      }

      const notificationKey = `${payload.sensor_id}-${payload.timestamp}`;

      if (this.recentNotifications.has(notificationKey)) {
        logger.debug(
          { sensorId: payload.sensor_id },
          'Debounced duplicate notification'
        );
        return;
      }

      this.recentNotifications.set(notificationKey, Date.now());

      const timeoutId = setTimeout(() => {
        this.recentNotifications.delete(notificationKey);
        this.debounceTimeouts.delete(notificationKey);
      }, this.debounceWindow);

      this.debounceTimeouts.set(notificationKey, timeoutId);

      const event = {
        sensorId: payload.sensor_id,
        sensorType: payload.sensor_type,
        value: parseFloat(payload.value),
        timestamp: new Date(payload.timestamp)
      };

      logger.info(event, 'Received sensor evaluation notification');
      this.emit('sensor_reading', event);
    } catch (error) {
      logger.error(
        { error, payload: msg.payload },
        'Failed to parse notification'
      );
    }
  }

  validatePayload(payload) {
    return (
      payload &&
      typeof payload.sensor_id === 'string' &&
      typeof payload.sensor_type === 'string' &&
      typeof payload.value !== 'undefined' &&
      payload.sensor_id.length > 0 &&
      payload.sensor_type.length > 0
    );
  }

  handleError(error) {
    logger.error({ error }, 'Sensor update listener connection error');
    this.isConnected = false;

    // Stop heartbeat
    this.stopHeartbeat();

    // Cleanup failed client before reconnecting
    this.cleanupClient();

    if (!this.isStopped) {
      this.scheduleReconnect();
    }

    // Emit error after scheduling reconnect to avoid unhandled errors in tests
    this.emit('error', error);
  }

  cleanupClient() {
    if (this.client) {
      try {
        this.client.removeAllListeners();
        this.client.end();
      } catch (error) {
        // Ignore cleanup errors
        logger.debug({ error }, 'Error during client cleanup');
      } finally {
        this.client = null;
      }
    }
  }

  clearDebounceMap() {
    // Clear all pending debounce timeouts
    for (const timeoutId of this.debounceTimeouts.values()) {
      clearTimeout(timeoutId);
    }
    this.debounceTimeouts.clear();
    this.recentNotifications.clear();
  }

  startHeartbeat() {
    // Periodically ping DB to detect silent disconnections
    this.heartbeatTimer = setInterval(async () => {
      if (!this.client || !this.isConnected) {
        return;
      }

      try {
        await this.client.query('SELECT 1');
        logger.debug('Listener heartbeat successful');
      } catch (error) {
        logger.warn({ error }, 'Listener heartbeat failed, reconnecting');
        this.handleError(error);
      }
    }, this.heartbeatInterval);
  }

  stopHeartbeat() {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  scheduleReconnect() {
    logger.info(
      { delay: this.reconnectDelay },
      'Scheduling reconnection attempt'
    );

    this.reconnectTimeout = setTimeout(async () => {
      if (!this.isStopped) {
        try {
          await this.start();
        } catch (error) {
          logger.error({ error }, 'Reconnection attempt failed');
        }
      }
    }, this.reconnectDelay);
  }

  async stop() {
    this.isStopped = true;

    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }

    // Stop heartbeat
    this.stopHeartbeat();

    // Clear all debounce timeouts
    this.clearDebounceMap();

    if (this.client && this.isConnected) {
      try {
        await this.client.query('UNLISTEN sensor_evaluation_needed');
        this.client.removeAllListeners();
        this.client.end();
        logger.info('Sensor update listener stopped');
      } catch (error) {
        logger.error({ error }, 'Error stopping sensor update listener');
      } finally {
        this.client = null;
        this.isConnected = false;
      }
    }
  }
}

module.exports = { SensorUpdateListener };
