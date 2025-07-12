// Common types used across microservices

export interface Pagination {
  page: number;
  limit: number;
  total: number;
  totalPages: number;
}

export interface PaginatedResponse<T> {
  data: T[];
  pagination: Pagination;
}

export interface ApiResponse<T = any> {
  success: boolean;
  data?: T;
  error?: {
    message: string;
    code?: string;
    details?: any;
  };
  metadata?: {
    timestamp: Date;
    version: string;
    requestId: string;
  };
}

export interface HealthCheckResponse {
  status: 'healthy' | 'unhealthy';
  service: string;
  version: string;
  timestamp: Date;
  checks?: Record<string, {
    status: 'up' | 'down';
    message?: string;
  }>;
}

export interface User {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  permissions: string[];
  createdAt: Date;
  updatedAt: Date;
}

export enum UserRole {
  ADMIN = 'ADMIN',
  OPERATOR = 'OPERATOR',
  VIEWER = 'VIEWER',
  SYSTEM = 'SYSTEM'
}

export interface JwtPayload {
  sub: string; // user id
  email: string;
  role: UserRole;
  permissions: string[];
  iat: number;
  exp: number;
}

// Sensor and SCADA types
export interface SensorReading {
  sensorId: string;
  timestamp: Date;
  value: number;
  unit: string;
  quality: DataQuality;
  metadata?: Record<string, any>;
}

export enum DataQuality {
  GOOD = 'GOOD',
  UNCERTAIN = 'UNCERTAIN',
  BAD = 'BAD',
  NOT_AVAILABLE = 'NOT_AVAILABLE'
}

export interface GateControl {
  gateId: string;
  position: number; // 0-100 (percentage)
  targetPosition?: number;
  status: GateStatus;
  lastUpdated: Date;
  operator?: string;
}

export enum GateStatus {
  OPEN = 'OPEN',
  CLOSED = 'CLOSED',
  OPENING = 'OPENING',
  CLOSING = 'CLOSING',
  STOPPED = 'STOPPED',
  ERROR = 'ERROR'
}

// Notification types
export interface Notification {
  id: string;
  type: NotificationType;
  severity: NotificationSeverity;
  title: string;
  message: string;
  timestamp: Date;
  acknowledged: boolean;
  acknowledgedBy?: string;
  acknowledgedAt?: Date;
  metadata?: Record<string, any>;
}

export enum NotificationType {
  ALARM = 'ALARM',
  WARNING = 'WARNING',
  INFO = 'INFO',
  SYSTEM = 'SYSTEM'
}

export enum NotificationSeverity {
  CRITICAL = 'CRITICAL',
  HIGH = 'HIGH',
  MEDIUM = 'MEDIUM',
  LOW = 'LOW'
}

// Audit log types
export interface AuditLog {
  id: string;
  userId: string;
  action: string;
  resource: string;
  resourceId?: string;
  timestamp: Date;
  ipAddress?: string;
  userAgent?: string;
  success: boolean;
  metadata?: Record<string, any>;
}