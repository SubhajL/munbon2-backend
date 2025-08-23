import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  UpdateDateColumn,
  Index,
} from 'typeorm';

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

@Entity('parcels_simple')
@Index(['parcelCode'], { unique: true })
@Index(['ownerId'])
@Index(['zoneId'])
@Index(['uploadId'])
export class ParcelSimple {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ name: 'parcel_code', unique: true })
  parcelCode: string;

  @Column({ name: 'upload_id' })
  uploadId: string;

  @Column({ name: 'zone_id' })
  zoneId: string;

  @Column({ type: 'jsonb' })
  geometry: any; // Store GeoJSON geometry

  @Column({ type: 'jsonb', nullable: true })
  centroid?: any; // Store point as JSON

  @Column({ type: 'float' })
  area: number; // Square meters

  @Column({ type: 'float', nullable: true })
  perimeter?: number; // Meters

  @Column({
    type: 'enum',
    enum: ParcelStatus,
    default: ParcelStatus.ACTIVE,
  })
  status: ParcelStatus;

  @Column({
    type: 'enum',
    enum: LandUseType,
    default: LandUseType.RICE,
    name: 'land_use_type',
  })
  landUseType: LandUseType;

  @Column({ name: 'owner_id', nullable: true })
  ownerId?: string;

  @Column({ name: 'owner_name', nullable: true })
  ownerName?: string;

  @Column({ name: 'crop_type', nullable: true })
  cropType?: string;

  @Column({ type: 'jsonb', nullable: true })
  attributes?: Record<string, any>;

  @Column({ type: 'jsonb', nullable: true })
  properties?: Record<string, any>;

  @CreateDateColumn({ name: 'created_at' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at' })
  updatedAt: Date;
}