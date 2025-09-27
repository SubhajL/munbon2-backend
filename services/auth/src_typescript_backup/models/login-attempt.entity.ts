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

export enum LoginAttemptStatus {
  SUCCESS = 'success',
  FAILED = 'failed',
  BLOCKED = 'blocked',
}

@Entity('login_attempts')
@Index(['email', 'createdAt'])
@Index(['ip', 'createdAt'])
export class LoginAttempt {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column()
  email: string;

  @Column({ nullable: true, name: 'user_id' })
  userId?: string;

  @ManyToOne(() => User, (user) => user.loginAttempts, { 
    nullable: true,
    onDelete: 'CASCADE' 
  })
  @JoinColumn({ name: 'user_id' })
  user?: User;

  @Column({
    type: 'enum',
    enum: LoginAttemptStatus,
  })
  status: LoginAttemptStatus;

  @Column()
  ip: string;

  @Column({ nullable: true, name: 'user_agent' })
  userAgent?: string;

  @Column({ nullable: true })
  reason?: string; // Reason for failure

  @Column({ nullable: true, name: 'country_code' })
  countryCode?: string;

  @Column({ nullable: true })
  city?: string;

  @Column({ type: 'jsonb', nullable: true })
  metadata?: Record<string, any>;

  @CreateDateColumn({ name: 'created_at' })
  createdAt: Date;
}