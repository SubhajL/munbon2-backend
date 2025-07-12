import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  UpdateDateColumn,
  ManyToMany,
  JoinTable,
  Index,
} from 'typeorm';
import { User } from './user.entity';
import { Permission } from './permission.entity';

@Entity('roles')
@Index(['name'], { unique: true })
export class Role {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ unique: true })
  name: string;

  @Column()
  displayName: string;

  @Column({ nullable: true })
  description?: string;

  @Column({ default: true })
  isActive: boolean;

  @Column({ default: false })
  isSystem: boolean; // System roles cannot be deleted

  @Column({ type: 'jsonb', nullable: true })
  metadata?: Record<string, any>;

  @ManyToMany(() => User, (user) => user.roles)
  users: User[];

  @ManyToMany(() => Permission, (permission) => permission.roles, { eager: true })
  @JoinTable({
    name: 'role_permissions',
    joinColumn: { name: 'role_id', referencedColumnName: 'id' },
    inverseJoinColumn: { name: 'permission_id', referencedColumnName: 'id' },
  })
  permissions: Permission[];

  @CreateDateColumn({ name: 'created_at' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at' })
  updatedAt: Date;

  hasPermission(permissionName: string): boolean {
    return this.permissions.some((permission) => permission.name === permissionName);
  }
}

// Predefined system roles
export const SYSTEM_ROLES = {
  SUPER_ADMIN: 'super_admin',
  RID_ADMIN: 'rid_admin',
  ZONE_MANAGER: 'zone_manager',
  GOVERNMENT_OFFICIAL: 'government_official',
  ORGANIZATION_ADMIN: 'organization_admin',
  FARMER_PREMIUM: 'farmer_premium',
  FARMER_BASIC: 'farmer_basic',
  RESEARCHER: 'researcher',
  GUEST: 'guest',
} as const;