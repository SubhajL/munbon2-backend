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
import { User } from './user.entity';

@Entity('sessions')
@Index(['sessionId'], { unique: true })
@Index(['userId', 'isActive'])
@Index(['expiresAt'])
export class Session {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ name: 'session_id', unique: true })
  sessionId: string;

  @Column({ name: 'user_id' })
  userId: string;

  @ManyToOne(() => User, { onDelete: 'CASCADE' })
  @JoinColumn({ name: 'user_id' })
  user: User;

  @Column({ type: 'jsonb' })
  data: Record<string, any>;

  @Column({ nullable: true })
  ip?: string;

  @Column({ nullable: true, name: 'user_agent' })
  userAgent?: string;

  @Column({ default: true, name: 'is_active' })
  isActive: boolean;

  @Column({ name: 'expires_at' })
  expiresAt: Date;

  @Column({ nullable: true, name: 'last_accessed_at' })
  lastAccessedAt?: Date;

  @CreateDateColumn({ name: 'created_at' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at' })
  updatedAt: Date;

  isExpired(): boolean {
    return this.expiresAt < new Date();
  }

  isValid(): boolean {
    return this.isActive && !this.isExpired();
  }
}