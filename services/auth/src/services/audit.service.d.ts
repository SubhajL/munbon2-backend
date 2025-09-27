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
declare class AuditService {
    private auditLogRepository;
    constructor();
    log(data: AuditLogData): Promise<void>;
    getUserAuditLogs(userId: string, limit?: number, offset?: number): Promise<AuditLog[]>;
    getResourceAuditLogs(resource: string, limit?: number, offset?: number): Promise<AuditLog[]>;
    getSecurityEvents(startDate: Date, endDate: Date): Promise<AuditLog[]>;
    getFailedLoginAttempts(email: string, since: Date): Promise<number>;
}
export declare const auditService: AuditService;
export {};
//# sourceMappingURL=audit.service.d.ts.map