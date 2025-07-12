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

@Entity('password_resets')
@Index(['token'], { unique: true })
@Index(['email', 'expiresAt'])
export class PasswordReset {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column()
  email: string;

  @Column({ name: 'user_id' })
  userId: string;

  @ManyToOne(() => User, { onDelete: 'CASCADE' })
  @JoinColumn({ name: 'user_id' })
  user: User;

  @Column({ unique: true })
  token: string;

  @Column({ name: 'expires_at' })
  expiresAt: Date;

  @Column({ default: false })
  used: boolean;

  @Column({ nullable: true, name: 'used_at' })
  usedAt?: Date;

  @Column({ nullable: true })
  ip?: string;

  @Column({ nullable: true, name: 'user_agent' })
  userAgent?: string;

  @CreateDateColumn({ name: 'created_at' })
  createdAt: Date;

  isExpired(): boolean {
    return this.expiresAt < new Date();
  }

  isValid(): boolean {
    return !this.used && !this.isExpired();
  }

  markAsUsed() {
    this.used = true;
    this.usedAt = new Date();
  }
}