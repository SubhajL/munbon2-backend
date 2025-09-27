import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  UpdateDateColumn,
  ManyToMany,
  JoinTable,
  OneToMany,
  Index,
  BeforeInsert,
  BeforeUpdate,
} from 'typeorm';
import { IsEmail, IsNotEmpty, MinLength } from 'class-validator';
import bcrypt from 'bcrypt';
import { config } from '../config';
import { Role } from './role.entity';
import { RefreshToken } from './refresh-token.entity';
import { LoginAttempt } from './login-attempt.entity';
import { AuditLog } from './audit-log.entity';

export enum UserStatus {
  ACTIVE = 'active',
  INACTIVE = 'inactive',
  LOCKED = 'locked',
  SUSPENDED = 'suspended',
}

export enum UserType {
  FARMER = 'farmer',
  GOVERNMENT_OFFICIAL = 'government_official',
  ORGANIZATION = 'organization',
  RESEARCHER = 'researcher',
  SYSTEM_ADMIN = 'system_admin',
}

@Entity('users')
@Index(['email'], { unique: true })
@Index(['citizenId'], { unique: true, where: 'citizen_id IS NOT NULL' })
@Index(['phoneNumber'], { unique: true, where: 'phone_number IS NOT NULL' })
export class User {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ unique: true })
  @IsEmail()
  email: string;

  @Column({ select: false })
  @MinLength(8)
  password: string;

  @Column()
  @IsNotEmpty()
  firstName: string;

  @Column()
  @IsNotEmpty()
  lastName: string;

  @Column({ nullable: true, name: 'citizen_id' })
  citizenId?: string;

  @Column({ nullable: true, name: 'phone_number' })
  phoneNumber?: string;

  @Column({
    type: 'enum',
    enum: UserType,
    default: UserType.FARMER,
  })
  userType: UserType;

  @Column({
    type: 'enum',
    enum: UserStatus,
    default: UserStatus.ACTIVE,
  })
  status: UserStatus;

  @Column({ default: false, name: 'email_verified' })
  emailVerified: boolean;

  @Column({ nullable: true, name: 'email_verified_at' })
  emailVerifiedAt?: Date;

  @Column({ default: false, name: 'two_factor_enabled' })
  twoFactorEnabled: boolean;

  @Column({ nullable: true, name: 'thai_digital_id' })
  thaiDigitalId?: string;

  @Column({ nullable: true, name: 'profile_image' })
  profileImage?: string;

  @Column({ type: 'jsonb', nullable: true })
  metadata?: Record<string, any>;

  @Column({ nullable: true, name: 'last_login_at' })
  lastLoginAt?: Date;

  @Column({ nullable: true, name: 'last_login_ip' })
  lastLoginIp?: string;

  @Column({ default: 0, name: 'failed_login_attempts' })
  failedLoginAttempts: number;

  @Column({ nullable: true, name: 'locked_until' })
  lockedUntil?: Date;

  @Column({ nullable: true, name: 'organization_id' })
  organizationId?: string;

  @Column({ nullable: true, name: 'zone_id' })
  zoneId?: string;

  @ManyToMany(() => Role, (role) => role.users, { eager: true })
  @JoinTable({
    name: 'user_roles',
    joinColumn: { name: 'user_id', referencedColumnName: 'id' },
    inverseJoinColumn: { name: 'role_id', referencedColumnName: 'id' },
  })
  roles: Role[];

  @OneToMany(() => RefreshToken, (token) => token.user)
  refreshTokens: RefreshToken[];

  @OneToMany(() => LoginAttempt, (attempt) => attempt.user)
  loginAttempts: LoginAttempt[];

  @OneToMany(() => AuditLog, (log) => log.user)
  auditLogs: AuditLog[];

  @CreateDateColumn({ name: 'created_at' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at' })
  updatedAt: Date;

  @BeforeInsert()
  @BeforeUpdate()
  async hashPassword() {
    if (this.password && !this.password.startsWith('$2b$')) {
      this.password = await bcrypt.hash(this.password, config.security.bcryptRounds);
    }
  }

  async comparePassword(password: string): Promise<boolean> {
    return bcrypt.compare(password, this.password);
  }

  hasRole(roleName: string): boolean {
    return this.roles.some((role) => role.name === roleName);
  }

  hasPermission(permissionName: string): boolean {
    return this.roles.some((role) =>
      role.permissions.some((permission) => permission.name === permissionName)
    );
  }

  isLocked(): boolean {
    return this.status === UserStatus.LOCKED || 
           (this.lockedUntil && this.lockedUntil > new Date());
  }

  toJSON() {
    const { password, ...user } = this;
    return user;
  }
}