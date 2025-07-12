// MongoDB initialization script for Munbon Irrigation System

// Switch to admin database for user creation
db = db.getSiblingDB('admin');

// Create application user
db.createUser({
  user: 'munbon_app',
  pwd: 'app_password',
  roles: [
    { role: 'readWrite', db: 'munbon_dev' },
    { role: 'readWrite', db: 'munbon_config' },
    { role: 'readWrite', db: 'munbon_logs' }
  ]
});

// Create read-only user for analytics
db.createUser({
  user: 'munbon_reader',
  pwd: 'readonly_password',
  roles: [
    { role: 'read', db: 'munbon_dev' },
    { role: 'read', db: 'munbon_config' },
    { role: 'read', db: 'munbon_logs' }
  ]
});

// Switch to main application database
db = db.getSiblingDB('munbon_dev');

// Create collections with validation schemas

// System configuration collection
db.createCollection('system_config', {
  validator: {
    $jsonSchema: {
      bsonType: 'object',
      required: ['key', 'value', 'service', 'version'],
      properties: {
        key: { bsonType: 'string' },
        value: { bsonType: 'object' },
        service: { bsonType: 'string' },
        version: { bsonType: 'int' },
        description: { bsonType: 'string' },
        is_active: { bsonType: 'bool' },
        created_at: { bsonType: 'date' },
        updated_at: { bsonType: 'date' }
      }
    }
  }
});

// Alert rules collection
db.createCollection('alert_rules', {
  validator: {
    $jsonSchema: {
      bsonType: 'object',
      required: ['name', 'condition', 'actions', 'severity'],
      properties: {
        name: { bsonType: 'string' },
        description: { bsonType: 'string' },
        condition: {
          bsonType: 'object',
          required: ['metric', 'operator', 'threshold'],
          properties: {
            metric: { bsonType: 'string' },
            operator: { enum: ['gt', 'lt', 'eq', 'gte', 'lte', 'ne'] },
            threshold: { bsonType: 'number' },
            duration_seconds: { bsonType: 'int' }
          }
        },
        actions: {
          bsonType: 'array',
          items: {
            bsonType: 'object',
            required: ['type'],
            properties: {
              type: { enum: ['email', 'sms', 'line', 'webhook'] },
              config: { bsonType: 'object' }
            }
          }
        },
        severity: { enum: ['critical', 'warning', 'info'] },
        is_enabled: { bsonType: 'bool' },
        tags: { bsonType: 'array', items: { bsonType: 'string' } },
        created_at: { bsonType: 'date' },
        updated_at: { bsonType: 'date' }
      }
    }
  }
});

// Notification templates collection
db.createCollection('notification_templates', {
  validator: {
    $jsonSchema: {
      bsonType: 'object',
      required: ['name', 'type', 'language', 'template'],
      properties: {
        name: { bsonType: 'string' },
        type: { enum: ['email', 'sms', 'line', 'push'] },
        language: { enum: ['th', 'en'] },
        subject: { bsonType: 'string' },
        template: { bsonType: 'string' },
        variables: {
          bsonType: 'array',
          items: { bsonType: 'string' }
        },
        is_active: { bsonType: 'bool' },
        created_at: { bsonType: 'date' },
        updated_at: { bsonType: 'date' }
      }
    }
  }
});

// Maintenance schedules collection
db.createCollection('maintenance_schedules', {
  validator: {
    $jsonSchema: {
      bsonType: 'object',
      required: ['equipment_id', 'maintenance_type', 'schedule'],
      properties: {
        equipment_id: { bsonType: 'string' },
        equipment_type: { bsonType: 'string' },
        maintenance_type: { enum: ['preventive', 'corrective', 'inspection'] },
        schedule: {
          bsonType: 'object',
          properties: {
            frequency: { enum: ['daily', 'weekly', 'monthly', 'quarterly', 'annually'] },
            next_date: { bsonType: 'date' },
            assigned_to: { bsonType: 'string' }
          }
        },
        history: {
          bsonType: 'array',
          items: {
            bsonType: 'object',
            properties: {
              performed_date: { bsonType: 'date' },
              performed_by: { bsonType: 'string' },
              notes: { bsonType: 'string' },
              issues_found: { bsonType: 'array' }
            }
          }
        },
        created_at: { bsonType: 'date' },
        updated_at: { bsonType: 'date' }
      }
    }
  }
});

// Report definitions collection
db.createCollection('report_definitions', {
  validator: {
    $jsonSchema: {
      bsonType: 'object',
      required: ['name', 'type', 'query', 'format'],
      properties: {
        name: { bsonType: 'string' },
        description: { bsonType: 'string' },
        type: { enum: ['operational', 'analytical', 'compliance', 'custom'] },
        query: { bsonType: 'object' },
        parameters: {
          bsonType: 'array',
          items: {
            bsonType: 'object',
            properties: {
              name: { bsonType: 'string' },
              type: { bsonType: 'string' },
              required: { bsonType: 'bool' },
              default_value: {}
            }
          }
        },
        format: { enum: ['pdf', 'excel', 'csv', 'json'] },
        schedule: {
          bsonType: 'object',
          properties: {
            enabled: { bsonType: 'bool' },
            cron: { bsonType: 'string' },
            recipients: { bsonType: 'array', items: { bsonType: 'string' } }
          }
        },
        created_at: { bsonType: 'date' },
        updated_at: { bsonType: 'date' }
      }
    }
  }
});

// File metadata collection
db.createCollection('file_metadata', {
  validator: {
    $jsonSchema: {
      bsonType: 'object',
      required: ['filename', 'file_type', 'size', 'storage_path'],
      properties: {
        filename: { bsonType: 'string' },
        original_name: { bsonType: 'string' },
        file_type: { bsonType: 'string' },
        mime_type: { bsonType: 'string' },
        size: { bsonType: 'long' },
        storage_path: { bsonType: 'string' },
        storage_type: { enum: ['s3', 'local', 'gridfs'] },
        checksum: { bsonType: 'string' },
        metadata: { bsonType: 'object' },
        tags: { bsonType: 'array', items: { bsonType: 'string' } },
        uploaded_by: { bsonType: 'string' },
        uploaded_at: { bsonType: 'date' },
        expires_at: { bsonType: 'date' }
      }
    }
  }
});

// Create indexes
db.system_config.createIndex({ key: 1, service: 1 }, { unique: true });
db.system_config.createIndex({ service: 1 });

db.alert_rules.createIndex({ name: 1 }, { unique: true });
db.alert_rules.createIndex({ 'condition.metric': 1 });
db.alert_rules.createIndex({ severity: 1, is_enabled: 1 });

db.notification_templates.createIndex({ name: 1, type: 1, language: 1 }, { unique: true });
db.notification_templates.createIndex({ type: 1, is_active: 1 });

db.maintenance_schedules.createIndex({ equipment_id: 1 });
db.maintenance_schedules.createIndex({ 'schedule.next_date': 1 });

db.report_definitions.createIndex({ name: 1 }, { unique: true });
db.report_definitions.createIndex({ type: 1 });

db.file_metadata.createIndex({ filename: 1 });
db.file_metadata.createIndex({ uploaded_at: -1 });
db.file_metadata.createIndex({ tags: 1 });

// Insert default configuration
db.system_config.insertMany([
  {
    key: 'irrigation.default_schedule',
    value: {
      morning: { start: '06:00', duration_minutes: 120 },
      evening: { start: '16:00', duration_minutes: 90 }
    },
    service: 'scheduling',
    version: 1,
    description: 'Default irrigation schedule',
    is_active: true,
    created_at: new Date(),
    updated_at: new Date()
  },
  {
    key: 'alerts.rate_limits',
    value: {
      sms_per_hour: 10,
      email_per_hour: 100,
      line_per_hour: 50
    },
    service: 'notification',
    version: 1,
    description: 'Alert notification rate limits',
    is_active: true,
    created_at: new Date(),
    updated_at: new Date()
  },
  {
    key: 'sensors.quality_thresholds',
    value: {
      water_level: { min: 0, max: 30, unit: 'cm' },
      moisture: { min: 0, max: 100, unit: '%' },
      flow_rate: { min: 0, max: 1000, unit: 'l/s' }
    },
    service: 'sensor-data',
    version: 1,
    description: 'Sensor data quality thresholds',
    is_active: true,
    created_at: new Date(),
    updated_at: new Date()
  }
]);

// Switch to config database
db = db.getSiblingDB('munbon_config');

// Create feature flags collection
db.createCollection('feature_flags', {
  validator: {
    $jsonSchema: {
      bsonType: 'object',
      required: ['name', 'enabled'],
      properties: {
        name: { bsonType: 'string' },
        description: { bsonType: 'string' },
        enabled: { bsonType: 'bool' },
        rollout_percentage: { bsonType: 'int', minimum: 0, maximum: 100 },
        environments: {
          bsonType: 'array',
          items: { enum: ['development', 'staging', 'production'] }
        },
        created_at: { bsonType: 'date' },
        updated_at: { bsonType: 'date' }
      }
    }
  }
});

db.feature_flags.createIndex({ name: 1 }, { unique: true });

// Insert default feature flags
db.feature_flags.insertMany([
  {
    name: 'ai_optimization',
    description: 'Enable AI-based water distribution optimization',
    enabled: false,
    rollout_percentage: 0,
    environments: ['development'],
    created_at: new Date(),
    updated_at: new Date()
  },
  {
    name: 'mobile_app_v2',
    description: 'Enable new mobile app features',
    enabled: true,
    rollout_percentage: 100,
    environments: ['development', 'staging', 'production'],
    created_at: new Date(),
    updated_at: new Date()
  }
]);

// Switch to logs database
db = db.getSiblingDB('munbon_logs');

// Create capped collection for audit logs (max 1GB)
db.createCollection('audit_logs', {
  capped: true,
  size: 1073741824,
  max: 1000000
});

// Create indexes for audit logs
db.audit_logs.createIndex({ timestamp: -1 });
db.audit_logs.createIndex({ user_id: 1 });
db.audit_logs.createIndex({ action: 1 });

print('MongoDB initialization completed successfully');