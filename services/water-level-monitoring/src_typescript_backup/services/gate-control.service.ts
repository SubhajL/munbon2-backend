import axios from 'axios';
import { config } from '../config';
import { logger } from '../utils/logger';
import { TimescaleService } from './timescale.service';
import { 
  GateControlRecommendation, 
  WaterLevelReading 
} from '../models/water-level.model';

export class GateControlService {
  constructor(
    private timescaleService: TimescaleService
  ) {}

  async generateRecommendation(
    gateId: string,
    sensorId: string,
    currentReading: WaterLevelReading
  ): Promise<GateControlRecommendation | null> {
    if (!config.gateControl.enabled) {
      return null;
    }
    
    const currentLevel = currentReading.levelCm;
    const targetLevel = (config.gateControl.minLevel + config.gateControl.maxLevel) / 2;
    
    // Get rate of change
    const rateOfChange = await this.timescaleService.getRateOfChange(sensorId, 30);
    
    // Determine action
    let action: 'open' | 'close' | 'maintain';
    let percentage: number;
    let reason: string;
    let confidence: number;
    
    if (currentLevel < config.gateControl.minLevel) {
      // Water too low - close gate to retain water
      action = 'close';
      const deficit = config.gateControl.minLevel - currentLevel;
      percentage = Math.min(100, (deficit / config.gateControl.minLevel) * 100);
      reason = `Water level ${currentLevel}cm is below minimum ${config.gateControl.minLevel}cm`;
      confidence = 0.9;
    } else if (currentLevel > config.gateControl.maxLevel) {
      // Water too high - open gate to release water
      action = 'open';
      const excess = currentLevel - config.gateControl.maxLevel;
      percentage = Math.min(100, (excess / config.gateControl.maxLevel) * 100);
      reason = `Water level ${currentLevel}cm exceeds maximum ${config.gateControl.maxLevel}cm`;
      confidence = 0.9;
    } else {
      // Water in acceptable range - check trend
      if (rateOfChange > 2) {
        // Rising rapidly
        action = 'open';
        percentage = Math.min(50, rateOfChange * 10);
        reason = `Water rising rapidly at ${rateOfChange.toFixed(2)}cm/hour`;
        confidence = 0.7;
      } else if (rateOfChange < -2) {
        // Falling rapidly
        action = 'close';
        percentage = Math.min(50, Math.abs(rateOfChange) * 10);
        reason = `Water falling rapidly at ${Math.abs(rateOfChange).toFixed(2)}cm/hour`;
        confidence = 0.7;
      } else {
        // Stable
        action = 'maintain';
        percentage = 0;
        reason = 'Water level stable within acceptable range';
        confidence = 0.95;
      }
    }
    
    // Estimate time to target
    let estimatedTimeToTarget: number | undefined;
    if (action !== 'maintain' && Math.abs(rateOfChange) > 0.1) {
      const levelDifference = Math.abs(targetLevel - currentLevel);
      estimatedTimeToTarget = (levelDifference / Math.abs(rateOfChange)) * 60; // minutes
    }
    
    const recommendation: GateControlRecommendation = {
      gateId,
      sensorId,
      currentLevel,
      targetLevel,
      recommendedAction: action,
      recommendedPercentage: Math.round(percentage),
      reason,
      confidence,
      estimatedTimeToTarget,
    };
    
    logger.info({ recommendation }, 'Generated gate control recommendation');
    
    // Send to SCADA service if configured
    if (config.services.scadaUrl && action !== 'maintain') {
      this.sendToScada(recommendation).catch(err => {
        logger.error({ err, recommendation }, 'Failed to send recommendation to SCADA');
      });
    }
    
    return recommendation;
  }

  private async sendToScada(recommendation: GateControlRecommendation): Promise<void> {
    try {
      await axios.post(`${config.services.scadaUrl}/api/v1/gate-control/recommendations`, {
        source: 'water-level-monitoring',
        recommendation,
        timestamp: new Date(),
      });
    } catch (error) {
      throw new Error(`Failed to send to SCADA service: ${error}`);
    }
  }

  async getGateStatus(gateId: string): Promise<any> {
    if (!config.services.scadaUrl) {
      throw new Error('SCADA service URL not configured');
    }
    
    try {
      const response = await axios.get(`${config.services.scadaUrl}/api/v1/gates/${gateId}/status`);
      return response.data;
    } catch (error) {
      logger.error({ error, gateId }, 'Failed to get gate status');
      throw error;
    }
  }
}