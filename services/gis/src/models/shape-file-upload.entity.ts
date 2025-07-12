import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  UpdateDateColumn,
} from 'typeorm';

export enum UploadStatus {
  PENDING = 'pending',
  PROCESSING = 'processing',
  COMPLETED = 'completed',
  FAILED = 'failed',
}

@Entity('shape_file_uploads')
export class ShapeFileUpload {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ name: 'upload_id', unique: true })
  uploadId: string;

  @Column({ name: 'file_name' })
  fileName: string;

  @Column({ name: 's3_key' })
  s3Key: string;

  @Column({
    type: 'enum',
    enum: UploadStatus,
    default: UploadStatus.PENDING,
  })
  status: UploadStatus;

  @Column({ type: 'jsonb', nullable: true })
  metadata?: Record<string, any>;

  @Column({ nullable: true })
  error?: string;

  @Column({ name: 'parcel_count', nullable: true })
  parcelCount?: number;

  @CreateDateColumn({ name: 'uploaded_at' })
  uploadedAt: Date;

  @UpdateDateColumn({ name: 'updated_at' })
  updatedAt: Date;

  @Column({ name: 'completed_at', nullable: true })
  completedAt?: Date;
}