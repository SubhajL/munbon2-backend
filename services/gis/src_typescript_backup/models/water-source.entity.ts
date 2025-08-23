import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  UpdateDateColumn,
  Index,
} from 'typeorm';
import { Geometry, Polygon, Point } from 'geojson';

export enum WaterSourceType {
  RESERVOIR = 'reservoir',
  RIVER = 'river',
  POND = 'pond',
  WELL = 'well',
  SPRING = 'spring',
  DAM = 'dam',
}

@Entity('water_sources')
@Index(['code'], { unique: true })
@Index(['type'])
export class WaterSource {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ unique: true })
  code: string;

  @Column()
  name: string;

  @Column({ name: 'name_th', nullable: true })
  nameTh?: string;

  @Column({
    type: 'enum',
    enum: WaterSourceType,
  })
  type: WaterSourceType;

  @Column({
    type: 'geometry',
    spatialFeatureType: 'Geometry',
    srid: 4326,
  })
  geometry: Polygon | Point;

  @Column({ type: 'float', nullable: true })
  area?: number; // Square meters (for polygons)

  @Column({ name: 'max_capacity', type: 'float', nullable: true })
  maxCapacity?: number; // Cubic meters

  @Column({ name: 'current_volume', type: 'float', nullable: true })
  currentVolume?: number; // Cubic meters

  @Column({ name: 'water_level', type: 'float', nullable: true })
  waterLevel?: number; // Meters

  @Column({ name: 'quality_index', type: 'float', nullable: true })
  qualityIndex?: number; // 0-100

  @Column({ type: 'jsonb', nullable: true })
  properties?: Record<string, any>;

  @CreateDateColumn({ name: 'created_at' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at' })
  updatedAt: Date;
}