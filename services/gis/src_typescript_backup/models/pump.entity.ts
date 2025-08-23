import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  UpdateDateColumn,
  Index,
} from 'typeorm';
import { Point } from 'geojson';

export enum PumpType {
  CENTRIFUGAL = 'centrifugal',
  SUBMERSIBLE = 'submersible',
  TURBINE = 'turbine',
  AXIAL_FLOW = 'axial_flow',
  MIXED_FLOW = 'mixed_flow',
}

export enum PumpStatus {
  OPERATIONAL = 'operational',
  STANDBY = 'standby',
  MAINTENANCE = 'maintenance',
  FAULTY = 'faulty',
  DECOMMISSIONED = 'decommissioned',
}

@Entity('control_structures')
@Index(['structureCode'], { unique: true })
export class Pump {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ name: 'structure_code', unique: true })
  structureCode: string; // e.g., 'P-Z1-001'

  @Column({ name: 'structure_name' })
  structureName: string;

  @Column({ name: 'structure_type' })
  structureType: string; // 'pump'

  @Column({ name: 'canal_id', nullable: true })
  canalId?: string;

  @Column({
    type: 'geometry',
    spatialFeatureType: 'Point',
    srid: 4326,
  })
  location: Point;

  @Column({ name: 'elevation_msl', type: 'float', nullable: true })
  elevationMsl?: number;

  @Column({ name: 'max_discharge_cms', type: 'float', nullable: true })
  maxDischargeCms?: number;

  @Column({ name: 'scada_tag', nullable: true })
  scadaTag?: string;

  @Column({ name: 'operational_status', nullable: true })
  operationalStatus?: string;

  @CreateDateColumn({ name: 'created_at' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at' })
  updatedAt: Date;
}