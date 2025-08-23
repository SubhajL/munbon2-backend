import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  UpdateDateColumn,
  OneToMany,
  Index,
} from 'typeorm';
import { Geometry, Polygon } from 'geojson';
import { Parcel } from './parcel.entity';
import { Canal } from './canal.entity';
import { IrrigationBlock } from './irrigation-block.entity';

export enum ZoneType {
  IRRIGATION = 'irrigation',
  ADMINISTRATIVE = 'administrative',
  WATERSHED = 'watershed',
  CULTIVATION = 'cultivation',
}

export enum ZoneStatus {
  ACTIVE = 'active',
  INACTIVE = 'inactive',
  MAINTENANCE = 'maintenance',
}

@Entity('irrigation_zones')
@Index(['zoneCode'], { unique: true })
export class Zone {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ name: 'zone_code', unique: true })
  zoneCode: string; // e.g., 'Z1', 'Z2', etc.

  @Column({ name: 'zone_name' })
  zoneName: string;

  @Column({ name: 'zone_type', nullable: true })
  zoneType?: string;

  @Column({ name: 'area_hectares', type: 'float' })
  areaHectares: number;

  @Column({
    type: 'geometry',
    spatialFeatureType: 'Polygon',
    srid: 4326,
  })
  boundary: Polygon;

  @OneToMany(() => Parcel, (parcel) => parcel.zone)
  parcels: Parcel[];

  @OneToMany(() => Canal, (canal) => canal.zone)
  canals: Canal[];

  @OneToMany(() => IrrigationBlock, (block) => block.zone)
  irrigationBlocks: IrrigationBlock[];

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
        zoneCode: this.zoneCode,
        zoneName: this.zoneName,
        zoneType: this.zoneType,
        areaHectares: this.areaHectares,
      },
    };
  }
}