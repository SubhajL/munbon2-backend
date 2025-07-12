// System-wide constants

export const SYSTEM_CONSTANTS = {
  // API versioning
  API_VERSION: 'v1',
  API_PREFIX: '/api/v1',
  
  // Default pagination
  DEFAULT_PAGE_SIZE: 20,
  MAX_PAGE_SIZE: 100,
  
  // Time constants
  CACHE_TTL: {
    SHORT: 60 * 1000, // 1 minute
    MEDIUM: 5 * 60 * 1000, // 5 minutes
    LONG: 60 * 60 * 1000, // 1 hour
    DAY: 24 * 60 * 60 * 1000 // 1 day
  },
  
  // Rate limiting
  RATE_LIMIT: {
    WINDOW_MS: 15 * 60 * 1000, // 15 minutes
    MAX_REQUESTS: 100,
    MAX_REQUESTS_AUTHENTICATED: 1000
  },
  
  // Security
  PASSWORD_MIN_LENGTH: 8,
  SESSION_TIMEOUT: 24 * 60 * 60 * 1000, // 24 hours
  
  // File upload
  MAX_FILE_SIZE: 10 * 1024 * 1024, // 10MB
  ALLOWED_FILE_TYPES: ['image/jpeg', 'image/png', 'application/pdf'],
  
  // Queue names
  QUEUES: {
    SENSOR_DATA: 'sensor-data-queue',
    NOTIFICATIONS: 'notification-queue',
    AUDIT_LOGS: 'audit-log-queue',
    ML_PREDICTIONS: 'ml-prediction-queue'
  },
  
  // Event names
  EVENTS: {
    SENSOR_READING_RECEIVED: 'sensor.reading.received',
    GATE_STATUS_CHANGED: 'gate.status.changed',
    ALARM_TRIGGERED: 'alarm.triggered',
    PREDICTION_COMPLETED: 'prediction.completed',
    USER_LOGIN: 'user.login',
    USER_LOGOUT: 'user.logout'
  },
  
  // HTTP status messages
  HTTP_MESSAGES: {
    200: 'OK',
    201: 'Created',
    204: 'No Content',
    400: 'Bad Request',
    401: 'Unauthorized',
    403: 'Forbidden',
    404: 'Not Found',
    409: 'Conflict',
    429: 'Too Many Requests',
    500: 'Internal Server Error',
    503: 'Service Unavailable'
  }
} as const;

// Sensor types
export const SENSOR_TYPES = {
  WATER_LEVEL: 'WATER_LEVEL',
  FLOW_RATE: 'FLOW_RATE',
  PRESSURE: 'PRESSURE',
  TEMPERATURE: 'TEMPERATURE',
  PH: 'PH',
  DISSOLVED_OXYGEN: 'DISSOLVED_OXYGEN',
  TURBIDITY: 'TURBIDITY',
  CONDUCTIVITY: 'CONDUCTIVITY'
} as const;

// Units of measurement
export const UNITS = {
  WATER_LEVEL: 'm',
  FLOW_RATE: 'm³/s',
  PRESSURE: 'kPa',
  TEMPERATURE: '°C',
  PH: 'pH',
  DISSOLVED_OXYGEN: 'mg/L',
  TURBIDITY: 'NTU',
  CONDUCTIVITY: 'μS/cm'
} as const;

// Permissions
export const PERMISSIONS = {
  // System
  SYSTEM_ADMIN: 'system:admin',
  SYSTEM_CONFIG: 'system:config',
  
  // Users
  USER_CREATE: 'user:create',
  USER_READ: 'user:read',
  USER_UPDATE: 'user:update',
  USER_DELETE: 'user:delete',
  
  // Sensors
  SENSOR_READ: 'sensor:read',
  SENSOR_WRITE: 'sensor:write',
  SENSOR_CONFIG: 'sensor:config',
  
  // Gates
  GATE_READ: 'gate:read',
  GATE_CONTROL: 'gate:control',
  GATE_CONFIG: 'gate:config',
  
  // Reports
  REPORT_READ: 'report:read',
  REPORT_CREATE: 'report:create',
  REPORT_EXPORT: 'report:export',
  
  // Alarms
  ALARM_READ: 'alarm:read',
  ALARM_ACKNOWLEDGE: 'alarm:acknowledge',
  ALARM_CONFIG: 'alarm:config'
} as const;

// Regex patterns
export const PATTERNS = {
  EMAIL: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
  PHONE_TH: /^(\+66|0)\d{9}$/,
  SENSOR_ID: /^SENSOR-[A-Z0-9]{8}$/,
  GATE_ID: /^GATE-[A-Z0-9]{6}$/
} as const;