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
import { Point } from 'geojson';
import { Canal } from './canal.entity';

export enum GateType {
  MAIN = 'main',
  CHECK = 'check',
  FARM = 'farm',
  REGULATOR = 'regulator',
  SPILLWAY = 'spillway',
  INTAKE = 'intake',
}

export enum GateStatus {
  OPERATIONAL = 'operational',
  MAINTENANCE = 'maintenance',
  FAULTY = 'faulty',
  CLOSED = 'closed',
}

export enum GateControlType {
  MANUAL = 'manual',
  ELECTRIC = 'electric',
  HYDRAULIC = 'hydraulic',
  PNEUMATIC = 'pneumatic',
  SCADA = 'scada',
}

@Entity('control_structures')
@Index(['structureCode'], { unique: true })
export class Gate {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ name: 'structure_code', unique: true })
  structureCode: string; // e.g., 'G-RMC-001'

  @Column({ name: 'structure_name' })
  structureName: string;

  @Column({ name: 'structure_type' })
  structureType: string; // 'gate', 'pump', etc.

  @Column({ name: 'canal_id', nullable: true })
  canalId?: string;

  @Column({
    type: 'geometry',
    spatialFeatureType: 'Point',
    srid: 4326,
  })
  location: Point;

  @Column({ name: 'elevation_msl', type: 'float', nullable: true })
  elevationMsl?: number; // Meters above sea level

  @Column({ name: 'max_discharge_cms', type: 'float', nullable: true })
  maxDischargeCms?: number;

  @Column({ name: 'scada_tag', nullable: true })
  scadaTag?: string;

  @Column({ name: 'operational_status', nullable: true })
  operationalStatus?: string;

  @ManyToOne(() => Canal, (canal) => canal.gates, { nullable: true })
  @JoinColumn({ name: 'canal_id' })
  canal?: Canal;

  @CreateDateColumn({ name: 'created_at' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at' })
  updatedAt: Date;

  // Virtual properties
  get geoJSON(): any {
    return {
      type: 'Feature',
      geometry: this.location,
      properties: {
        id: this.id,
        structureCode: this.structureCode,
        structureName: this.structureName,
        structureType: this.structureType,
        elevationMsl: this.elevationMsl,
        maxDischargeCms: this.maxDischargeCms,
        scadaTag: this.scadaTag,
        operationalStatus: this.operationalStatus,
      },
    };
  }
}