// Mock pg Client
const mockClient = {
  connect: jest.fn(),
  query: jest.fn(),
  on: jest.fn(),
  removeAllListeners: jest.fn(),
  end: jest.fn()
};

const MockClient = jest.fn(() => mockClient);

jest.mock('pg', () => ({
  Client: MockClient
}));

const { SensorUpdateListener } = require('../sensorUpdateListener');

describe('SensorUpdateListener', () => {
  let listener;
  let connectionConfig;

  beforeEach(() => {
    jest.clearAllMocks();
    mockClient.connect.mockResolvedValue(undefined);
    mockClient.query.mockResolvedValue({ rows: [] });
    
    connectionConfig = {
      host: 'localhost',
      port: 5432,
      database: 'test_db',
      user: 'test_user',
      password: 'test_pass'
    };

    listener = new SensorUpdateListener(connectionConfig, {
      reconnectDelay: 100,
      debounceWindow: 1000,
      heartbeatInterval: 5000
    });
  });

  afterEach(async () => {
    if (listener) {
      await listener.stop();
    }
  });

  describe('constructor', () => {
    test('stores connection config', () => {
      expect(listener.connectionConfig).toEqual(connectionConfig);
    });

    test('initializes with default options', () => {
      const defaultListener = new SensorUpdateListener(connectionConfig);
      expect(defaultListener.reconnectDelay).toBe(5000);
      expect(defaultListener.debounceWindow).toBe(5000);
      expect(defaultListener.heartbeatInterval).toBe(30000);
    });

    test('accepts custom options', () => {
      expect(listener.reconnectDelay).toBe(100);
      expect(listener.debounceWindow).toBe(1000);
      expect(listener.heartbeatInterval).toBe(5000);
    });
  });

  describe('start', () => {
    test('creates dedicated Client with correct config', async () => {
      await listener.start();

      expect(MockClient).toHaveBeenCalledWith({
        host: 'localhost',
        port: 5432,
        database: 'test_db',
        user: 'test_user',
        password: 'test_pass',
        keepAlive: true,
        statement_timeout: 0,
        query_timeout: 0,
        application_name: 'smartfarm-water-control-listener'
      });
      expect(mockClient.connect).toHaveBeenCalled();
    });

    test('sets session idle timeouts to zero', async () => {
      await listener.start();

      expect(mockClient.query).toHaveBeenCalledWith('SET idle_session_timeout = 0');
      expect(mockClient.query).toHaveBeenCalledWith('SET idle_in_transaction_session_timeout = 0');
    });

    test('executes LISTEN command', async () => {
      await listener.start();

      expect(mockClient.query).toHaveBeenCalledWith('LISTEN sensor_evaluation_needed');
    });

    test('attaches notification and error handlers', async () => {
      await listener.start();

      expect(mockClient.on).toHaveBeenCalledWith('notification', expect.any(Function));
      expect(mockClient.on).toHaveBeenCalledWith('error', expect.any(Function));
    });

    test('does not reconnect if already connected', async () => {
      await listener.start();
      jest.clearAllMocks();

      await listener.start();

      expect(MockClient).not.toHaveBeenCalled();
    });

    test('cleans up on connection failure', async () => {
      mockClient.connect.mockRejectedValueOnce(new Error('Connection failed'));

      await expect(listener.start()).rejects.toThrow('Connection failed');
      expect(listener.isConnected).toBe(false);
    });
  });

  describe('validatePayload', () => {
    test('accepts valid payload', () => {
      const payload = {
        sensor_id: '0001-0001',
        sensor_type: 'moisture',
        value: 75.5,
        timestamp: '2025-10-23T10:00:00Z'
      };

      expect(listener.validatePayload(payload)).toBe(true);
    });

    test('rejects payload without sensor_id', () => {
      const payload = { sensor_type: 'moisture', value: 75.5 };
      expect(listener.validatePayload(payload)).toBe(false);
    });

    test('rejects payload without sensor_type', () => {
      const payload = { sensor_id: '0001-0001', value: 75.5 };
      expect(listener.validatePayload(payload)).toBe(false);
    });

    test('rejects payload without value', () => {
      const payload = { sensor_id: '0001-0001', sensor_type: 'moisture' };
      expect(listener.validatePayload(payload)).toBe(false);
    });

    test('rejects payload with empty sensor_id', () => {
      const payload = { sensor_id: '', sensor_type: 'moisture', value: 75.5 };
      expect(listener.validatePayload(payload)).toBe(false);
    });

    test('rejects payload with empty sensor_type', () => {
      const payload = { sensor_id: '0001-0001', sensor_type: '', value: 75.5 };
      expect(listener.validatePayload(payload)).toBe(false);
    });

    test('rejects null payload', () => {
      expect(listener.validatePayload(null)).toBeFalsy();
    });
  });

  describe('handleNotification', () => {
    test('emits sensor_reading event for valid notification', async () => {
      await listener.start();

      const emitSpy = jest.spyOn(listener, 'emit');
      const payload = {
        sensor_id: '0001-0001',
        sensor_type: 'moisture',
        value: 75.5,
        timestamp: '2025-10-23T10:00:00Z'
      };

      listener.handleNotification({
        channel: 'sensor_evaluation_needed',
        payload: JSON.stringify(payload)
      });

      expect(emitSpy).toHaveBeenCalledWith('sensor_reading', {
        sensorId: '0001-0001',
        sensorType: 'moisture',
        value: 75.5,
        timestamp: new Date('2025-10-23T10:00:00Z')
      });
    });

    test('debounces duplicate notifications', async () => {
      await listener.start();

      const emitSpy = jest.spyOn(listener, 'emit');
      const payload = {
        sensor_id: '0001-0001',
        sensor_type: 'moisture',
        value: 75.5,
        timestamp: '2025-10-23T10:00:00Z'
      };

      listener.handleNotification({
        channel: 'sensor_evaluation_needed',
        payload: JSON.stringify(payload)
      });

      listener.handleNotification({
        channel: 'sensor_evaluation_needed',
        payload: JSON.stringify(payload)
      });

      expect(emitSpy).toHaveBeenCalledTimes(1);
    });

    test('ignores notifications from wrong channel', async () => {
      await listener.start();

      const emitSpy = jest.spyOn(listener, 'emit');

      listener.handleNotification({
        channel: 'other_channel',
        payload: JSON.stringify({ sensor_id: '0001-0001' })
      });

      expect(emitSpy).not.toHaveBeenCalled();
    });

    test('ignores invalid payloads', async () => {
      await listener.start();

      const emitSpy = jest.spyOn(listener, 'emit');

      listener.handleNotification({
        channel: 'sensor_evaluation_needed',
        payload: JSON.stringify({ invalid: 'data' })
      });

      expect(emitSpy).not.toHaveBeenCalled();
    });
  });

  describe('cleanupClient', () => {
    test('calls client.end() not release()', async () => {
      await listener.start();

      listener.cleanupClient();

      expect(mockClient.end).toHaveBeenCalled();
      expect(mockClient.removeAllListeners).toHaveBeenCalled();
      expect(listener.client).toBe(null);
    });

    test('handles cleanup errors gracefully', async () => {
      await listener.start();
      mockClient.end.mockImplementationOnce(() => {
        throw new Error('Cleanup error');
      });

      expect(() => listener.cleanupClient()).not.toThrow();
      expect(listener.client).toBe(null);
    });

    test('does nothing if no client exists', () => {
      expect(() => listener.cleanupClient()).not.toThrow();
    });
  });

  describe('stop', () => {
    test('executes UNLISTEN and ends connection', async () => {
      await listener.start();

      await listener.stop();

      expect(mockClient.query).toHaveBeenCalledWith('UNLISTEN sensor_evaluation_needed');
      expect(mockClient.end).toHaveBeenCalled();
      expect(listener.isConnected).toBe(false);
      expect(listener.isStopped).toBe(true);
    });

    test('clears reconnect timeout', async () => {
      await listener.start();
      listener.reconnectTimeout = setTimeout(() => {}, 5000);

      await listener.stop();

      expect(listener.reconnectTimeout).toBe(null);
    });

    test('stops heartbeat', async () => {
      await listener.start();
      expect(listener.heartbeatTimer).not.toBe(null);

      await listener.stop();

      expect(listener.heartbeatTimer).toBe(null);
    });
  });

  describe('heartbeat', () => {
    test('detects failed connection and triggers reconnect', async () => {
      jest.useFakeTimers();
      listener.isStopped = true; // Prevent reconnection loop
      await listener.start();

      // Add error handler to prevent unhandled error
      listener.on('error', () => {});

      const handleErrorSpy = jest.spyOn(listener, 'handleError');
      mockClient.query.mockRejectedValueOnce(new Error('Connection lost'));

      // Advance timers and wait for promises to settle
      jest.advanceTimersByTime(5000);
      await Promise.resolve(); // Let microtasks flush

      expect(handleErrorSpy).toHaveBeenCalled();

      jest.useRealTimers();
    });
  });

  describe('scheduleReconnect', () => {
    test('retries connection after delay', () => {
      jest.useFakeTimers();

      listener.isStopped = false;
      listener.scheduleReconnect();

      expect(listener.reconnectTimeout).not.toBe(null);

      jest.advanceTimersByTime(100);
      jest.runOnlyPendingTimers();

      expect(mockClient.connect).toHaveBeenCalled();

      jest.useRealTimers();
    });

    test('does not retry if stopped', () => {
      jest.useFakeTimers();

      listener.isStopped = true;
      listener.scheduleReconnect();

      jest.advanceTimersByTime(100);
      jest.runOnlyPendingTimers();

      expect(mockClient.connect).not.toHaveBeenCalled();

      jest.useRealTimers();
    });
  });
});
