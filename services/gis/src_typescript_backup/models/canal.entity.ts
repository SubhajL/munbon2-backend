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
import { Geometry, LineString, Point } from 'geojson';
import { Zone } from './zone.entity';
import { Gate } from './gate.entity';

export enum CanalType {
  MAIN = 'main',
  LATERAL = 'lateral',
  SUB_LATERAL = 'sub_lateral',
  FIELD = 'field',
  DRAINAGE = 'drainage',
}

export enum CanalStatus {
  OPERATIONAL = 'operational',
  MAINTENANCE = 'maintenance',
  DAMAGED = 'damaged',
  ABANDONED = 'abandoned',
}

export enum CanalCondition {
  EXCELLENT = 'excellent',
  GOOD = 'good',
  FAIR = 'fair',
  POOR = 'poor',
  CRITICAL = 'critical',
}

@Entity('canal_network')
@Index(['canalCode'], { unique: true })
export class Canal {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ name: 'canal_code', unique: true })
  canalCode: string; // e.g., 'RMC', '1L-RMC', '2L-RMC'

  @Column({ name: 'canal_name' })
  canalName: string;

  @Column({ name: 'canal_type', nullable: true })
  canalType?: string;

  @Column({ name: 'length_meters', type: 'float' })
  lengthMeters: number;

  @Column({ name: 'width_meters', type: 'float', nullable: true })
  widthMeters?: number;

  @Column({ name: 'depth_meters', type: 'float', nullable: true })
  depthMeters?: number;

  @Column({ name: 'capacity_cms', type: 'float', nullable: true })
  capacityCms?: number; // Cubic meters per second

  @Column({
    type: 'geometry',
    spatialFeatureType: 'LineString',
    srid: 4326,
  })
  geometry: LineString;

  @Column({ name: 'upstream_node_id', nullable: true })
  upstreamNodeId?: string;

  @Column({ name: 'downstream_node_id', nullable: true })
  downstreamNodeId?: string;

  @ManyToOne(() => Zone, (zone) => zone.canals, { nullable: true })
  zone?: Zone;

  @OneToMany(() => Gate, (gate) => gate.canal)
  gates: Gate[];

  @CreateDateColumn({ name: 'created_at' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at' })
  updatedAt: Date;

  // Virtual properties
  get geoJSON(): any {
    return {
      type: 'Feature',
      geometry: this.geometry,
      properties: {
        id: this.id,
        canalCode: this.canalCode,
        canalName: this.canalName,
        canalType: this.canalType,
        lengthMeters: this.lengthMeters,
        widthMeters: this.widthMeters,
        depthMeters: this.depthMeters,
        capacityCms: this.capacityCms,
      },
    };
  }
}