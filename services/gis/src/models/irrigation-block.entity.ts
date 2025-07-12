import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  UpdateDateColumn,
  ManyToOne,
  OneToMany,
  JoinColumn,
  Index,
} from 'typeorm';
import { Polygon } from 'geojson';
import { Zone } from './zone.entity';
import { Parcel } from './parcel.entity';

@Entity('irrigation_blocks')
@Index(['code'], { unique: true })
@Index(['zoneId'])
export class IrrigationBlock {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ unique: true })
  code: string; // e.g., 'IB-Z1-01'

  @Column()
  name: string;

  @Column({
    type: 'geometry',
    spatialFeatureType: 'Polygon',
    srid: 4326,
  })
  geometry: Polygon;

  @Column({ type: 'float' })
  area: number; // Square meters

  @Column({ name: 'zone_id' })
  zoneId: string;

  @ManyToOne(() => Zone, (zone) => zone.irrigationBlocks)
  @JoinColumn({ name: 'zone_id' })
  zone: Zone;

  // @OneToMany(() => Parcel, (parcel) => parcel.irrigationBlock)
  // parcels: Parcel[];

  @Column({ name: 'water_allocation', type: 'float', nullable: true })
  waterAllocation?: number; // Cubic meters per day

  @Column({ name: 'irrigation_schedule', type: 'jsonb', nullable: true })
  irrigationSchedule?: Array<{
    dayOfWeek: number;
    startTime: string;
    endTime: string;
    allocation: number;
  }>;

  @Column({ type: 'jsonb', nullable: true })
  properties?: Record<string, any>;

  @CreateDateColumn({ name: 'created_at' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at' })
  updatedAt: Date;
}