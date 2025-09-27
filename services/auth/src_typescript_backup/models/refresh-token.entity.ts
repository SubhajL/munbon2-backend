import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  ManyToOne,
  JoinColumn,
  Index,
} from 'typeorm';
import { User } from './user.entity';

@Entity('refresh_tokens')
@Index(['token'], { unique: true })
@Index(['userId', 'isActive'])
@Index(['expiresAt'])
export class RefreshToken {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ unique: true })
  token: string;

  @Column({ name: 'user_id' })
  userId: string;

  @ManyToOne(() => User, (user) => user.refreshTokens, { onDelete: 'CASCADE' })
  @JoinColumn({ name: 'user_id' })
  user: User;

  @Column({ nullable: true, name: 'device_id' })
  deviceId?: string;

  @Column({ nullable: true, name: 'device_name' })
  deviceName?: string;

  @Column({ nullable: true, name: 'user_agent' })
  userAgent?: string;

  @Column({ nullable: true })
  ip?: string;

  @Column({ default: true, name: 'is_active' })
  isActive: boolean;

  @Column({ name: 'expires_at' })
  expiresAt: Date;

  @Column({ nullable: true, name: 'revoked_at' })
  revokedAt?: Date;

  @Column({ nullable: true, name: 'revoked_by' })
  revokedBy?: string;

  @Column({ nullable: true, name: 'revoke_reason' })
  revokeReason?: string;

  @CreateDateColumn({ name: 'created_at' })
  createdAt: Date;

  isExpired(): boolean {
    return this.expiresAt < new Date();
  }

  isValid(): boolean {
    return this.isActive && !this.isExpired() && !this.revokedAt;
  }

  revoke(userId: string, reason?: string) {
    this.isActive = false;
    this.revokedAt = new Date();
    this.revokedBy = userId;
    this.revokeReason = reason;
  }
}