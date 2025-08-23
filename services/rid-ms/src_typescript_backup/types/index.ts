import { Feature, FeatureCollection, Polygon, MultiPolygon } from 'geojson';

export interface ShapeFileMetadata {
  id: string;
  originalFileName: string;
  uploadDate: Date;
  processedDate?: Date;
  status: 'pending' | 'processing' | 'processed' | 'failed';
  error?: string;
  fileSize: number;
  featureCount?: number;
  boundingBox?: BoundingBox;
  coordinateSystem: string;
  attributes?: string[];
}

export interface BoundingBox {
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
}

export interface ParcelData {
  id: string;
  parcelId: string;
  geometry: Polygon | MultiPolygon;
  area: number; // in square meters
  zone?: string;
  subZone?: string;
  landUseType?: string;
  cropType?: string;
  plantingDate?: Date;
  harvestDate?: Date;
  owner?: string;
  waterDemandMethod: 'RID-MS' | 'ROS' | 'AWD';
  waterDemand?: WaterDemand;
  attributes: Record<string, any>;
}

export interface WaterDemand {
  method: 'RID-MS' | 'ROS' | 'AWD';
  dailyDemand: number; // cubic meters per day
  weeklyDemand: number; // cubic meters per week
  monthlyDemand: number; // cubic meters per month
  seasonalDemand: number; // cubic meters per season
  cropCoefficient?: number;
  referenceEvapotranspiration?: number;
  irrigationEfficiency?: number;
  lastCalculated: Date;
  parameters?: Record<string, any>;
}

export interface ProcessingResult {
  shapeFileId: string;
  success: boolean;
  parcelsProcessed: number;
  parcelsWithErrors: number;
  processingTime: number; // milliseconds
  errors?: ProcessingError[];
}

export interface ProcessingError {
  parcelId?: string;
  errorCode: string;
  message: string;
  details?: any;
}

export interface WaterDemandRequest {
  parcels: string[]; // Array of parcel IDs
  method: 'RID-MS' | 'ROS' | 'AWD';
  parameters?: {
    cropType?: string;
    plantingDate?: Date;
    irrigationEfficiency?: number;
    [key: string]: any;
  };
}

export interface WaterDemandResponse {
  requestId: string;
  parcels: ParcelWaterDemand[];
  totalDailyDemand: number;
  totalWeeklyDemand: number;
  totalMonthlyDemand: number;
  calculatedAt: Date;
}

export interface ParcelWaterDemand {
  parcelId: string;
  area: number;
  method: string;
  waterDemand: WaterDemand;
}

export interface ShapeFileUploadRequest {
  fileName: string;
  description?: string;
  waterDemandMethod?: 'RID-MS' | 'ROS' | 'AWD';
  processingInterval?: 'daily' | 'weekly' | 'bi-weekly';
}

export interface GeoJSONExport {
  type: 'FeatureCollection';
  features: Feature<Polygon | MultiPolygon, ParcelData>[];
  crs?: {
    type: string;
    properties: {
      name: string;
    };
  };
}

export interface ZoneStatistics {
  zone: string;
  totalArea: number;
  parcelCount: number;
  waterDemandMethods: {
    'RID-MS': number;
    'ROS': number;
    'AWD': number;
  };
  totalWaterDemand: {
    daily: number;
    weekly: number;
    monthly: number;
  };
  cropTypes: Record<string, number>;
}