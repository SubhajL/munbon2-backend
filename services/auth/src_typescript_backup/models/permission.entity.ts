import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  UpdateDateColumn,
  ManyToMany,
  Index,
} from 'typeorm';
import { Role } from './role.entity';

@Entity('permissions')
@Index(['name'], { unique: true })
@Index(['resource', 'action'])
export class Permission {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ unique: true })
  name: string; // e.g., 'sensors.read', 'gates.control'

  @Column()
  displayName: string;

  @Column({ nullable: true })
  description?: string;

  @Column()
  resource: string; // e.g., 'sensors', 'gates', 'users'

  @Column()
  action: string; // e.g., 'read', 'write', 'delete', 'control'

  @Column({ default: true })
  isActive: boolean;

  @Column({ type: 'jsonb', nullable: true })
  conditions?: Record<string, any>; // For attribute-based access control

  @ManyToMany(() => Role, (role) => role.permissions)
  roles: Role[];

  @CreateDateColumn({ name: 'created_at' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at' })
  updatedAt: Date;
}

// Predefined permissions
export const PERMISSIONS = {
  // System
  SYSTEM_ADMIN: 'system.admin',
  SYSTEM_CONFIG: 'system.config',
  
  // Users
  USERS_READ: 'users.read',
  USERS_WRITE: 'users.write',
  USERS_DELETE: 'users.delete',
  USERS_MANAGE_ROLES: 'users.manage_roles',
  
  // Sensors
  SENSORS_READ: 'sensors.read',
  SENSORS_WRITE: 'sensors.write',
  SENSORS_DELETE: 'sensors.delete',
  SENSORS_CALIBRATE: 'sensors.calibrate',
  
  // Water Control
  GATES_READ: 'gates.read',
  GATES_CONTROL: 'gates.control',
  PUMPS_READ: 'pumps.read',
  PUMPS_CONTROL: 'pumps.control',
  VALVES_READ: 'valves.read',
  VALVES_CONTROL: 'valves.control',
  
  // GIS
  GIS_READ: 'gis.read',
  GIS_WRITE: 'gis.write',
  GIS_ADMIN: 'gis.admin',
  
  // Reports
  REPORTS_READ: 'reports.read',
  REPORTS_GENERATE: 'reports.generate',
  REPORTS_EXPORT: 'reports.export',
  
  // AI Models
  AI_READ: 'ai.read',
  AI_EXECUTE: 'ai.execute',
  AI_TRAIN: 'ai.train',
  
  // Irrigation
  IRRIGATION_VIEW_SCHEDULE: 'irrigation.view_schedule',
  IRRIGATION_CREATE_SCHEDULE: 'irrigation.create_schedule',
  IRRIGATION_MODIFY_SCHEDULE: 'irrigation.modify_schedule',
  IRRIGATION_DELETE_SCHEDULE: 'irrigation.delete_schedule',
  
  // Alerts
  ALERTS_READ: 'alerts.read',
  ALERTS_ACKNOWLEDGE: 'alerts.acknowledge',
  ALERTS_CONFIGURE: 'alerts.configure',
} as const;