import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  UpdateDateColumn,
  OneToOne,
  JoinColumn,
  Index,
} from 'typeorm';
import { User } from './user.entity';

@Entity('two_factor_secrets')
@Index(['userId'], { unique: true })
export class TwoFactorSecret {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ name: 'user_id', unique: true })
  userId: string;

  @OneToOne(() => User, { onDelete: 'CASCADE' })
  @JoinColumn({ name: 'user_id' })
  user: User;

  @Column()
  secret: string;

  @Column({ name: 'backup_codes', type: 'text', array: true })
  backupCodes: string[];

  @Column({ name: 'used_backup_codes', type: 'text', array: true, default: [] })
  usedBackupCodes: string[];

  @Column({ default: false })
  verified: boolean;

  @Column({ nullable: true, name: 'verified_at' })
  verifiedAt?: Date;

  @Column({ nullable: true, name: 'last_used_at' })
  lastUsedAt?: Date;

  @CreateDateColumn({ name: 'created_at' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at' })
  updatedAt: Date;

  useBackupCode(code: string): boolean {
    const index = this.backupCodes.indexOf(code);
    if (index > -1 && !this.usedBackupCodes.includes(code)) {
      this.usedBackupCodes.push(code);
      this.lastUsedAt = new Date();
      return true;
    }
    return false;
  }

  hasUnusedBackupCodes(): boolean {
    return this.backupCodes.length > this.usedBackupCodes.length;
  }
}