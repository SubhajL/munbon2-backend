"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.auditService = void 0;
const database_1 = require("../config/database");
const audit_log_entity_1 = require("../models/audit-log.entity");
class AuditService {
    auditLogRepository;
    constructor() {
        this.auditLogRepository = database_1.AppDataSource.getRepository(audit_log_entity_1.AuditLog);
    }
    async log(data) {
        try {
            const auditLog = this.auditLogRepository.create(data);
            await this.auditLogRepository.save(auditLog);
        }
        catch (error) {
            console.error('Failed to create audit log:', error);
            console.error('Audit data:', data);
        }
    }
    async getUserAuditLogs(userId, limit = 50, offset = 0) {
        return this.auditLogRepository.find({
            where: { userId },
            order: { createdAt: 'DESC' },
            take: limit,
            skip: offset,
        });
    }
    async getResourceAuditLogs(resource, limit = 50, offset = 0) {
        return this.auditLogRepository.find({
            where: { resource },
            order: { createdAt: 'DESC' },
            take: limit,
            skip: offset,
            relations: ['user'],
        });
    }
    async getSecurityEvents(startDate, endDate) {
        const securityActions = [
            audit_log_entity_1.AuditAction.LOGIN_FAILED,
            audit_log_entity_1.AuditAction.SUSPICIOUS_ACTIVITY,
            audit_log_entity_1.AuditAction.ACCESS_DENIED,
            audit_log_entity_1.AuditAction.USER_LOCK,
            audit_log_entity_1.AuditAction.PASSWORD_RESET_REQUEST,
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
    async getFailedLoginAttempts(email, since) {
        const count = await this.auditLogRepository
            .createQueryBuilder('audit')
            .where('audit.action = :action', { action: audit_log_entity_1.AuditAction.LOGIN_FAILED })
            .andWhere('audit.metadata ->> \'email\' = :email', { email })
            .andWhere('audit.createdAt >= :since', { since })
            .getCount();
        return count;
    }
}
exports.auditService = new AuditService();
//# sourceMappingURL=audit.service.js.map