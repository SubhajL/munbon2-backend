import dotenv from 'dotenv';
import path from 'path';

// Load environment variables
dotenv.config({ path: path.join(__dirname, '../../.env.local') });

export const config = {
  service: {
    name: process.env.SERVICE_NAME || 'ros-service',
    port: parseInt(process.env.PORT || '3047', 10),
    env: process.env.NODE_ENV || 'development',
  },
  database: {
    host: process.env.DB_HOST || 'localhost',
    port: parseInt(process.env.DB_PORT || '5434', 10),
    name: process.env.DB_NAME || 'munbon_ros',
    user: process.env.DB_USER || 'postgres',
    password: process.env.DB_PASSWORD || 'postgres123',
  },
  calculation: {
    defaultAltitude: parseFloat(process.env.DEFAULT_ALTITUDE || '200'),
    defaultLatitude: parseFloat(process.env.DEFAULT_LATITUDE || '14.88'),
    defaultLongitude: parseFloat(process.env.DEFAULT_LONGITUDE || '102.02'),
    psychrometricConstant: parseFloat(process.env.PSYCHROMETRIC_CONSTANT || '0.665'),
  },
  irrigation: {
    surfaceEfficiency: parseFloat(process.env.SURFACE_IRRIGATION_EFFICIENCY || '0.65'),
    sprinklerEfficiency: parseFloat(process.env.SPRINKLER_EFFICIENCY || '0.85'),
    dripEfficiency: parseFloat(process.env.DRIP_EFFICIENCY || '0.95'),
    defaultEfficiency: parseFloat(process.env.DEFAULT_EFFICIENCY || '0.65'),
  },
  soil: {
    defaultType: process.env.DEFAULT_SOIL_TYPE || 'clay_loam',
    fieldCapacity: parseFloat(process.env.FIELD_CAPACITY || '0.35'),
    wiltingPoint: parseFloat(process.env.WILTING_POINT || '0.15'),
    totalAvailableWater: parseFloat(process.env.TOTAL_AVAILABLE_WATER || '200'),
  },
  mad: {
    vegetables: parseFloat(process.env.MAD_VEGETABLES || '0.50'),
    grainCrops: parseFloat(process.env.MAD_GRAIN_CROPS || '0.55'),
    rice: parseFloat(process.env.MAD_RICE || '0.20'),
    default: parseFloat(process.env.MAD_DEFAULT || '0.50'),
  },
  externalServices: {
    weather: process.env.WEATHER_SERVICE_URL || 'http://localhost:3006',
    gis: process.env.GIS_SERVICE_URL || 'http://localhost:3007',
    moisture: process.env.MOISTURE_SERVICE_URL || 'http://localhost:3005',
  },
  redis: {
    host: process.env.REDIS_HOST || 'localhost',
    port: parseInt(process.env.REDIS_PORT || '6379', 10),
    db: parseInt(process.env.REDIS_DB || '4', 10),
    ttl: {
      eto: parseInt(process.env.CACHE_TTL_ETO || '3600', 10),
      kc: parseInt(process.env.CACHE_TTL_KC || '86400', 10),
    },
  },
};