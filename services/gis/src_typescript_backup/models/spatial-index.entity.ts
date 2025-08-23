import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  Index,
} from 'typeorm';
import { Polygon } from 'geojson';

@Entity('spatial_indexes')
@Index(['entityType', 'entityId'], { unique: true })
@Index(['tileX', 'tileY', 'zoom'])
export class SpatialIndex {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ name: 'entity_type' })
  entityType: string; // 'zone', 'parcel', 'canal', etc.

  @Column({ name: 'entity_id' })
  entityId: string;

  @Column({
    type: 'geometry',
    spatialFeatureType: 'Polygon',
    srid: 4326,
  })
  bounds: Polygon;

  @Column({ name: 'tile_x', type: 'int' })
  tileX: number;

  @Column({ name: 'tile_y', type: 'int' })
  tileY: number;

  @Column({ type: 'int' })
  zoom: number;

  @Column({ name: 'min_zoom', type: 'int', default: 1 })
  minZoom: number;

  @Column({ name: 'max_zoom', type: 'int', default: 18 })
  maxZoom: number;

  @CreateDateColumn({ name: 'created_at' })
  createdAt: Date;
}