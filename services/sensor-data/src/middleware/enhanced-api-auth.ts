import { Request, Response, NextFunction } from 'express';
import { Logger } from 'pino';

interface ApiKeyConfig {
  key: string;
  name: string;
  organization: string;
  allowedDataTypes?: ('water_level' | 'moisture' | 'aos')[];
  allowedZones?: string[];
  rateLimit?: {
    requestsPerHour: number;
    requestsPerMinute: number;
  };
  expiresAt?: Date;
}

export class EnhancedApiAuth {
  private apiKeys: Map<string, ApiKeyConfig> = new Map();
  private logger: Logger;

  constructor(logger: Logger) {
    this.logger = logger;
    this.loadApiKeys();
  }

  private loadApiKeys() {
    // Load from environment or database
    const apiKeysJson = process.env.API_KEYS_CONFIG || '[]';
    
    // Default API keys for different organizations
    const defaultKeys: ApiKeyConfig[] = [
      {
        key: 'rid-ms-prod-' + this.generateSecureKey(),
        name: 'RID-MS Production',
        organization: 'Royal Irrigation Department',
        allowedDataTypes: ['water_level', 'moisture', 'aos'],
        allowedZones: ['Zone 1', 'Zone 2', 'Zone 3', 'Zone 4', 'Zone 5', 'Zone 6'],
        rateLimit: {
          requestsPerHour: 10000,
          requestsPerMinute: 200
        }
      },
      {
        key: 'rid-ms-dev-' + this.generateSecureKey(),
        name: 'RID-MS Development',
        organization: 'Royal Irrigation Department',
        allowedDataTypes: ['water_level', 'moisture', 'aos'],
        allowedZones: ['Zone 1', 'Zone 2'], // Limited zones for dev
        rateLimit: {
          requestsPerHour: 1000,
          requestsPerMinute: 50
        }
      },
      {
        key: 'tmd-weather-' + this.generateSecureKey(),
        name: 'Thai Meteorological Department',
        organization: 'TMD',
        allowedDataTypes: ['aos'], // Only weather data
        rateLimit: {
          requestsPerHour: 5000,
          requestsPerMinute: 100
        }
      },
      {
        key: 'research-uni-' + this.generateSecureKey(),
        name: 'University Research',
        organization: 'Kasetsart University',
        allowedDataTypes: ['moisture'], // Only moisture for agricultural research
        allowedZones: ['Zone 1'],
        rateLimit: {
          requestsPerHour: 500,
          requestsPerMinute: 20
        },
        expiresAt: new Date('2025-12-31') // Temporary access
      },
      {
        key: 'mobile-app-' + this.generateSecureKey(),
        name: 'Munbon Mobile App',
        organization: 'Munbon Project',
        allowedDataTypes: ['water_level', 'moisture'],
        rateLimit: {
          requestsPerHour: 50000, // Higher for mobile app
          requestsPerMinute: 1000
        }
      }
    ];

    // Load custom keys from environment if available
    try {
      const customKeys = JSON.parse(apiKeysJson) as ApiKeyConfig[];
      defaultKeys.push(...customKeys);
    } catch (error) {
      this.logger.warn('Failed to parse custom API keys from environment');
    }

    // Store all keys
    defaultKeys.forEach(config => {
      this.apiKeys.set(config.key, config);
    });

    // Log loaded keys (without exposing the actual keys)
    this.logger.info(`Loaded ${this.apiKeys.size} API keys`);
    this.apiKeys.forEach((config, key) => {
      this.logger.info({
        organization: config.organization,
        name: config.name,
        keyPrefix: key.substring(0, 10) + '...'
      }, 'API key loaded');
    });
  }

  private generateSecureKey(): string {
    // Generate a secure random key
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    let key = '';
    for (let i = 0; i < 32; i++) {
      key += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return key;
  }

  middleware() {
    return async (req: Request, res: Response, next: NextFunction): Promise<void> => {
      const apiKey = req.headers['x-api-key'] as string;

      if (!apiKey) {
        res.status(401).json({ 
          error: 'API key required',
          message: 'Include X-API-Key header with your request'
        });
        return;
      }

      const keyConfig = this.apiKeys.get(apiKey);

      if (!keyConfig) {
        this.logger.warn({ apiKey: apiKey.substring(0, 10) + '...' }, 'Invalid API key attempt');
        res.status(401).json({ error: 'Invalid API key' });
        return;
      }

      // Check expiration
      if (keyConfig.expiresAt && new Date() > keyConfig.expiresAt) {
        res.status(401).json({ 
          error: 'API key expired',
          message: 'Please contact support for renewal'
        });
        return;
      }

      // Check data type access
      const requestPath = req.path;
      let requestedDataType: string | null = null;

      if (requestPath.includes('/water-levels')) {
        requestedDataType = 'water_level';
      } else if (requestPath.includes('/moisture')) {
        requestedDataType = 'moisture';
      } else if (requestPath.includes('/aos')) {
        requestedDataType = 'aos';
      }

      if (requestedDataType && keyConfig.allowedDataTypes && 
          !keyConfig.allowedDataTypes.includes(requestedDataType as any)) {
        res.status(403).json({ 
          error: 'Access denied',
          message: `Your API key does not have access to ${requestedDataType} data`
        });
        return;
      }

      // Add key info to request for logging
      (req as any).apiKeyInfo = {
        organization: keyConfig.organization,
        name: keyConfig.name,
        allowedDataTypes: keyConfig.allowedDataTypes,
        allowedZones: keyConfig.allowedZones
      };

      // Log API usage
      this.logger.info({
        organization: keyConfig.organization,
        name: keyConfig.name,
        path: req.path,
        method: req.method,
        ip: req.ip
      }, 'API request');

      next();
    };
  }

  // Helper method to check zone access within route handlers
  checkZoneAccess(req: Request, zone: string): boolean {
    const keyInfo = (req as any).apiKeyInfo;
    if (!keyInfo || !keyInfo.allowedZones) {
      return true; // No zone restrictions
    }
    return keyInfo.allowedZones.includes(zone);
  }

  // Method to generate new API keys
  generateApiKey(config: Omit<ApiKeyConfig, 'key'>): ApiKeyConfig {
    const newKey = {
      ...config,
      key: `${config.organization.toLowerCase().replace(/\s+/g, '-')}-${this.generateSecureKey()}`
    };
    this.apiKeys.set(newKey.key, newKey);
    return newKey;
  }

  // Method to list all keys (for admin)
  listApiKeys(): Array<Omit<ApiKeyConfig, 'key'> & { keyPrefix: string }> {
    return Array.from(this.apiKeys.values()).map(config => ({
      keyPrefix: config.key.substring(0, 15) + '...',
      name: config.name,
      organization: config.organization,
      allowedDataTypes: config.allowedDataTypes,
      allowedZones: config.allowedZones,
      rateLimit: config.rateLimit,
      expiresAt: config.expiresAt
    }));
  }
}

// Singleton instance
let authInstance: EnhancedApiAuth | null = null;

export function getEnhancedApiAuth(logger: Logger): EnhancedApiAuth {
  if (!authInstance) {
    authInstance = new EnhancedApiAuth(logger);
  }
  return authInstance;
}