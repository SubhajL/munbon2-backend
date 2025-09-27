import { Repository } from 'typeorm';
import { AppDataSource } from '../config/database';
import { AuditLog, AuditAction } from '../models/audit-log.entity';

interface AuditLogData {
  userId?: string;
  action: AuditAction;
  resource?: string;
  description?: string;
  ip?: string;
  userAgent?: string;
  oldValues?: Record<string, any>;
  newValues?: Record<string, any>;
  metadata?: Record<string, any>;
  success: boolean;
  errorMessage?: string;
}

class AuditService {
  private auditLogRepository: Repository<AuditLog>;

  constructor() {
    this.auditLogRepository = AppDataSource.getRepository(AuditLog);
  }

  async log(data: AuditLogData): Promise<void> {
    try {
      const auditLog = this.auditLogRepository.create(data);
      await this.auditLogRepository.save(auditLog);
    } catch (error) {
      // Log to console if database logging fails
      console.error('Failed to create audit log:', error);
      console.error('Audit data:', data);
    }
  }

  async getUserAuditLogs(
    userId: string,
    limit: number = 50,
    offset: number = 0
  ): Promise<AuditLog[]> {
    return this.auditLogRepository.find({
      where: { userId },
      order: { createdAt: 'DESC' },
      take: limit,
      skip: offset,
    });
  }

  async getResourceAuditLogs(
    resource: string,
    limit: number = 50,
    offset: number = 0
  ): Promise<AuditLog[]> {
    return this.auditLogRepository.find({
      where: { resource },
      order: { createdAt: 'DESC' },
      take: limit,
      skip: offset,
      relations: ['user'],
    });
  }

  async getSecurityEvents(
    startDate: Date,
    endDate: Date
  ): Promise<AuditLog[]> {
    const securityActions = [
      AuditAction.LOGIN_FAILED,
      AuditAction.SUSPICIOUS_ACTIVITY,
      AuditAction.ACCESS_DENIED,
      AuditAction.USER_LOCK,
      AuditAction.PASSWORD_RESET_REQUEST,
    ];

    return this.auditLogRepository
      .createQueryBuilder('audit')
      .where('audit.action IN (:...actions)', { actions: securityActions })
      .andWhere('audit.createdAt BETWEEN :startDate AND :endDate', {
        startDate,
        endDate,
      })
      .orderBy('audit.createdAt', 'DESC')
      .getMany();
  }

  async getFailedLoginAttempts(
    email: string,
    since: Date
  ): Promise<number> {
    const count = await this.auditLogRepository
      .createQueryBuilder('audit')
      .where('audit.action = :action', { action: AuditAction.LOGIN_FAILED })
      .andWhere('audit.metadata ->> \'email\' = :email', { email })
      .andWhere('audit.createdAt >= :since', { since })
      .getCount();

    return count;
  }
}

export const auditService = new AuditService();