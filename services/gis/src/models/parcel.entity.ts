import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  UpdateDateColumn,
  ManyToOne,
  JoinColumn,
  Index,
} from 'typeorm';
import { Geometry, Polygon, Point } from 'geojson';
import { Zone } from './zone.entity';
import { IrrigationBlock } from './irrigation-block.entity';

export enum ParcelStatus {
  ACTIVE = 'active',
  INACTIVE = 'inactive',
  ABANDONED = 'abandoned',
  CONVERTING = 'converting',
}

export enum LandUseType {
  RICE = 'rice',
  VEGETABLE = 'vegetable',
  FRUIT = 'fruit',
  AQUACULTURE = 'aquaculture',
  LIVESTOCK = 'livestock',
  MIXED = 'mixed',
  FALLOW = 'fallow',
  OTHER = 'other',
}

export enum IrrigationMethod {
  FLOODING = 'flooding',
  FURROW = 'furrow',
  SPRINKLER = 'sprinkler',
  DRIP = 'drip',
  CENTER_PIVOT = 'center_pivot',
  MANUAL = 'manual',
}

@Entity('agricultural_plots')
@Index(['plotCode'], { unique: true })
@Index(['farmerId'])
@Index(['zoneId'])
export class Parcel {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ name: 'plot_code', unique: true })
  plotCode: string; // e.g., 'P-Z1-001'

  @Column({ name: 'farmer_id' })
  farmerId: string;

  @Column({ name: 'zone_id' })
  zoneId: string;

  @Column({ name: 'area_hectares', type: 'float' })
  areaHectares: number;

  @Column({
    type: 'geometry',
    spatialFeatureType: 'Geometry',
    srid: 4326,
  })
  boundary: Geometry;

  @Column({ name: 'current_crop_type', nullable: true })
  currentCropType?: string;

  @Column({ name: 'planting_date', nullable: true })
  plantingDate?: Date;

  @Column({ name: 'expected_harvest_date', nullable: true })
  expectedHarvestDate?: Date;

  @Column({ name: 'soil_type', nullable: true })
  soilType?: string;

  @Column({ 
    name: 'properties', 
    type: 'jsonb', 
    nullable: true,
    comment: 'Additional properties including RID attributes, water demand, etc.'
  })
  properties?: {
    uploadId?: string;
    ridAttributes?: {
      parcelAreaRai?: number;
      dataDateProcess?: Date;
      startInt?: Date;
      wpet?: number;
      age?: number;
      wprod?: number;
      plantId?: string;
      yieldAtMcKgpr?: number;
      seasonIrrM3PerRai?: number;
      autoNote?: string;
    };
    waterLevel?: number;
    cropHeight?: number;
    lastUpdated?: Date;
  };

  @ManyToOne(() => Zone, (zone) => zone.parcels)
  @JoinColumn({ name: 'zone_id' })
  zone: Zone;

  @CreateDateColumn({ name: 'created_at' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at' })
  updatedAt: Date;

  // Virtual properties
  get geoJSON(): any {
    return {
      type: 'Feature',
      geometry: this.boundary,
      properties: {
        id: this.id,
        plotCode: this.plotCode,
        areaHectares: this.areaHectares,
        currentCropType: this.currentCropType,
        farmerId: this.farmerId,
        soilType: this.soilType,
        plantingDate: this.plantingDate,
        expectedHarvestDate: this.expectedHarvestDate,
      },
    };
  }
}