import { PoolConfig } from 'pg';
import { Logger } from 'pino';
import { TimescaleRepository } from './timescale.repository';
import { 
  SensorReading, 
  WaterLevelReading, 
  MoistureReading,
  SensorRegistry,
  SensorLocationHistory,
  SensorType
} from '../models/sensor.model';

export interface DualWriteConfig {
  local: PoolConfig;
  ec2: PoolConfig;
  enableDualWrite: boolean;
  ec2WriteTimeout?: number; // milliseconds
  retryAttempts?: number;
  retryDelay?: number; // milliseconds
}

export interface WriteResult {
  local: { success: boolean; error?: any };
  ec2: { success: boolean; error?: any };
}

export class DualWriteRepository {
  private localRepo: TimescaleRepository;
  private ec2Repo: TimescaleRepository;
  private config: DualWriteConfig;
  private logger: Logger;

  constructor(config: DualWriteConfig, logger: Logger) {
    this.config = config;
    this.logger = logger.child({ module: 'DualWriteRepository' });
    
    // Initialize repositories
    this.localRepo = new TimescaleRepository(config.local);
    this.ec2Repo = new TimescaleRepository(config.ec2);
  }

  async initialize(): Promise<void> {
    this.logger.info('Initializing dual-write repositories...');
    
    // Always initialize local
    await this.localRepo.initialize();
    this.logger.info('Local repository initialized');
    
    // Initialize EC2 if dual-write is enabled
    if (this.config.enableDualWrite) {
      try {
        // For EC2, we skip table creation since tables already exist
        // Just test the connection
        await this.ec2Repo.query('SELECT 1');
        this.logger.info('EC2 repository connection verified');
      } catch (error) {
        this.logger.error({ error }, 'Failed to connect to EC2 repository - continuing with local only');
        // Don't throw - allow system to work with local only
      }
    }
  }

  // Helper method for dual writes with retry logic
  private async ensureSensorRegistered(sensorId: string, sensorType: string): Promise<void> {
    // Only ensure registration for EC2 if dual-write is enabled
    if (!this.config.enableDualWrite || !sensorId) {
      return;
    }

    try {
      // Update sensor registry for EC2 only (local doesn't have FK constraints)
      const sensorRegistry: Partial<SensorRegistry> = {
        sensorId: sensorId,
        sensorType: sensorType as SensorType,
        lastSeen: new Date(),
        metadata: {},
        isActive: true
      };

      // Directly update EC2 sensor registry to avoid circular dependency
      await this.ec2Repo.updateSensorRegistry(sensorRegistry);
    } catch (error) {
      // Log but don't fail the write operation
      this.logger.debug({ sensorId, sensorType, error }, 
        'Sensor registration update for EC2 (expected for existing sensors)');
    }
  }

  private async dualWrite<T>(
    operation: string,
    writeFunc: (repo: TimescaleRepository) => Promise<T>
  ): Promise<WriteResult> {
    const result: WriteResult = {
      local: { success: false },
      ec2: { success: false }
    };

    // Always write to local first
    try {
      await writeFunc(this.localRepo);
      result.local.success = true;
      this.logger.debug({ operation }, 'Local write successful');
    } catch (error) {
      result.local.error = error;
      this.logger.error({ error, operation }, 'Local write failed');
      // If local fails, don't attempt EC2
      return result;
    }

    // Write to EC2 if enabled and local succeeded
    if (this.config.enableDualWrite) {
      const maxAttempts = this.config.retryAttempts || 3;
      const retryDelay = this.config.retryDelay || 1000;

      for (let attempt = 1; attempt <= maxAttempts; attempt++) {
        try {
          // Use timeout for EC2 writes
          const timeoutPromise = new Promise((_, reject) => {
            setTimeout(() => reject(new Error('EC2 write timeout')), 
              this.config.ec2WriteTimeout || 5000);
          });

          await Promise.race([
            writeFunc(this.ec2Repo),
            timeoutPromise
          ]);

          result.ec2.success = true;
          this.logger.debug({ operation, attempt }, 'EC2 write successful');
          break;
        } catch (error) {
          result.ec2.error = error;
          this.logger.warn({ 
            error, 
            operation, 
            attempt, 
            maxAttempts 
          }, 'EC2 write failed');

          if (attempt < maxAttempts) {
            await new Promise(resolve => setTimeout(resolve, retryDelay * attempt));
          }
        }
      }

      // Log EC2 write failure but don't throw
      if (!result.ec2.success) {
        this.logger.error({ 
          operation, 
          error: result.ec2.error 
        }, 'EC2 write failed after all retries');
      }
    }

    return result;
  }

  // Sensor reading methods
  async saveSensorReading(reading: SensorReading): Promise<WriteResult> {
    // Ensure sensor is registered before writing data
    await this.ensureSensorRegistered(reading.sensorId, reading.sensorType);
    
    return this.dualWrite('saveSensorReading', 
      (repo) => repo.saveSensorReading(reading)
    );
  }

  async saveWaterLevelReading(reading: WaterLevelReading): Promise<WriteResult> {
    // Ensure sensor is registered before writing data
    await this.ensureSensorRegistered(reading.sensorId, 'water_level');
    
    return this.dualWrite('saveWaterLevelReading', 
      (repo) => repo.saveWaterLevelReading(reading)
    );
  }

  async saveMoistureReading(reading: MoistureReading): Promise<WriteResult> {
    // Ensure sensor is registered before writing data
    await this.ensureSensorRegistered(reading.sensorId, 'moisture');
    
    return this.dualWrite('saveMoistureReading', 
      (repo) => repo.saveMoistureReading(reading)
    );
  }

  async updateSensorRegistry(sensor: Partial<SensorRegistry>): Promise<WriteResult> {
    return this.dualWrite('updateSensorRegistry', 
      (repo) => repo.updateSensorRegistry(sensor)
    );
  }

  async addLocationHistory(history: SensorLocationHistory): Promise<WriteResult> {
    return this.dualWrite('addLocationHistory', 
      (repo) => repo.addLocationHistory(history)
    );
  }

  // Read methods - always from local
  async getSensorReadings(
    sensorId: string, 
    startTime: Date, 
    endTime: Date,
    aggregation?: string
  ): Promise<any[]> {
    return this.localRepo.getSensorReadings(sensorId, startTime, endTime, aggregation);
  }

  async getActiveSensors(): Promise<any[]> {
    return this.localRepo.getActiveSensors();
  }

  async getSensorsByLocation(lat: number, lng: number, radiusKm: number): Promise<any[]> {
    return this.localRepo.getSensorsByLocation(lat, lng, radiusKm);
  }

  // Transaction support - local only for now
  async executeInTransaction<T>(
    callback: (client: any) => Promise<T>
  ): Promise<T> {
    return this.localRepo.executeInTransaction(callback);
  }

  // Monitoring methods
  async getWriteStats(): Promise<{
    localWrites: number;
    ec2Writes: number;
    ec2Failures: number;
    dualWriteEnabled: boolean;
  }> {
    // This would ideally be tracked with metrics, but for now return config state
    return {
      localWrites: 0, // Would track this
      ec2Writes: 0,   // Would track this
      ec2Failures: 0, // Would track this
      dualWriteEnabled: this.config.enableDualWrite
    };
  }

  // Utility methods
  async query(text: string, params?: any[]): Promise<any> {
    return this.localRepo.query(text, params);
  }

  async close(): Promise<void> {
    await this.localRepo.close();
    if (this.config.enableDualWrite) {
      await this.ec2Repo.close();
    }
  }

  // Feature flag control
  enableDualWrite(): void {
    this.config.enableDualWrite = true;
    this.logger.info('Dual-write enabled');
  }

  disableDualWrite(): void {
    this.config.enableDualWrite = false;
    this.logger.info('Dual-write disabled');
  }

  isDualWriteEnabled(): boolean {
    return this.config.enableDualWrite;
  }
}