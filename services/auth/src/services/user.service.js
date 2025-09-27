"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.userService = void 0;
const typeorm_1 = require("typeorm");
const database_1 = require("../config/database");
const user_entity_1 = require("../models/user.entity");
const role_entity_1 = require("../models/role.entity");
const permission_entity_1 = require("../models/permission.entity");
const audit_service_1 = require("./audit.service");
const audit_log_entity_1 = require("../models/audit-log.entity");
const exceptions_1 = require("../utils/exceptions");
class UserService {
    userRepository;
    roleRepository;
    permissionRepository;
    constructor() {
        this.userRepository = database_1.AppDataSource.getRepository(user_entity_1.User);
        this.roleRepository = database_1.AppDataSource.getRepository(role_entity_1.Role);
        this.permissionRepository = database_1.AppDataSource.getRepository(permission_entity_1.Permission);
    }
    async findById(id) {
        const user = await this.userRepository.findOne({
            where: { id },
            relations: ['roles', 'roles.permissions'],
        });
        if (!user) {
            throw new exceptions_1.NotFoundException('User not found');
        }
        return user;
    }
    async findByEmail(email) {
        return this.userRepository.findOne({
            where: { email },
            relations: ['roles', 'roles.permissions'],
        });
    }
    async findByCitizenId(citizenId) {
        return this.userRepository.findOne({
            where: { citizenId },
            relations: ['roles', 'roles.permissions'],
        });
    }
    async findAll(filter, pagination) {
        const where = {};
        if (filter.status)
            where.status = filter.status;
        if (filter.userType)
            where.userType = filter.userType;
        if (filter.organizationId)
            where.organizationId = filter.organizationId;
        if (filter.zoneId)
            where.zoneId = filter.zoneId;
        const searchConditions = [];
        if (filter.search) {
            searchConditions.push({ email: (0, typeorm_1.ILike)(`%${filter.search}%`) }, { firstName: (0, typeorm_1.ILike)(`%${filter.search}%`) }, { lastName: (0, typeorm_1.ILike)(`%${filter.search}%`) }, { citizenId: (0, typeorm_1.ILike)(`%${filter.search}%`) }, { phoneNumber: (0, typeorm_1.ILike)(`%${filter.search}%`) });
        }
        const [users, total] = await this.userRepository.findAndCount({
            where: searchConditions.length > 0 ? searchConditions : where,
            relations: ['roles'],
            skip: (pagination.page - 1) * pagination.limit,
            take: pagination.limit,
            order: {
                createdAt: 'DESC',
            },
        });
        let filteredUsers = users;
        if (filter.roleId) {
            filteredUsers = users.filter(user => user.roles.some(role => role.id === filter.roleId));
        }
        return {
            data: filteredUsers,
            total,
            page: pagination.page,
            limit: pagination.limit,
            totalPages: Math.ceil(total / pagination.limit),
        };
    }
    async update(id, data, updatedBy) {
        const user = await this.findById(id);
        if (data.phoneNumber && data.phoneNumber !== user.phoneNumber) {
            const existing = await this.userRepository.findOne({
                where: { phoneNumber: data.phoneNumber },
            });
            if (existing) {
                throw new exceptions_1.ConflictException('Phone number already in use');
            }
        }
        const oldValues = {
            firstName: user.firstName,
            lastName: user.lastName,
            phoneNumber: user.phoneNumber,
            userType: user.userType,
            organizationId: user.organizationId,
            zoneId: user.zoneId,
        };
        Object.assign(user, data);
        await this.userRepository.save(user);
        await audit_service_1.auditService.log({
            userId: updatedBy,
            action: audit_log_entity_1.AuditAction.USER_UPDATE,
            resource: `user:${id}`,
            description: 'User updated',
            oldValues,
            newValues: data,
            success: true,
        });
        return user;
    }
    async updateStatus(id, status, updatedBy, reason) {
        const user = await this.findById(id);
        const oldStatus = user.status;
        user.status = status;
        if (status === user_entity_1.UserStatus.LOCKED) {
            user.lockedUntil = new Date(Date.now() + 24 * 60 * 60 * 1000);
        }
        else {
            user.lockedUntil = null;
            user.failedLoginAttempts = 0;
        }
        await this.userRepository.save(user);
        let action;
        if (status === user_entity_1.UserStatus.LOCKED) {
            action = audit_log_entity_1.AuditAction.USER_LOCK;
        }
        else if (oldStatus === user_entity_1.UserStatus.LOCKED && status === user_entity_1.UserStatus.ACTIVE) {
            action = audit_log_entity_1.AuditAction.USER_UNLOCK;
        }
        else {
            action = audit_log_entity_1.AuditAction.USER_UPDATE;
        }
        await audit_service_1.auditService.log({
            userId: updatedBy,
            action,
            resource: `user:${id}`,
            description: reason || `User status changed to ${status}`,
            oldValues: { status: oldStatus },
            newValues: { status },
            success: true,
        });
        return user;
    }
    async delete(id, deletedBy) {
        const user = await this.findById(id);
        if (user.hasRole(role_entity_1.SYSTEM_ROLES.SUPER_ADMIN)) {
            throw new exceptions_1.BadRequestException('Cannot delete system administrator');
        }
        await this.userRepository.remove(user);
        await audit_service_1.auditService.log({
            userId: deletedBy,
            action: audit_log_entity_1.AuditAction.USER_DELETE,
            resource: `user:${id}`,
            description: 'User deleted',
            metadata: { deletedUser: user.email },
            success: true,
        });
    }
    async assignRole(userId, roleId, assignedBy) {
        const user = await this.findById(userId);
        const role = await this.roleRepository.findOne({
            where: { id: roleId },
            relations: ['permissions'],
        });
        if (!role) {
            throw new exceptions_1.NotFoundException('Role not found');
        }
        if (user.roles.some(r => r.id === roleId)) {
            throw new exceptions_1.ConflictException('User already has this role');
        }
        user.roles.push(role);
        await this.userRepository.save(user);
        await audit_service_1.auditService.log({
            userId: assignedBy,
            action: audit_log_entity_1.AuditAction.ROLE_ASSIGN,
            resource: `user:${userId}`,
            description: `Assigned role ${role.name} to user`,
            metadata: { roleId, roleName: role.name },
            success: true,
        });
        return user;
    }
    async revokeRole(userId, roleId, revokedBy) {
        const user = await this.findById(userId);
        const roleIndex = user.roles.findIndex(r => r.id === roleId);
        if (roleIndex === -1) {
            throw new exceptions_1.BadRequestException('User does not have this role');
        }
        const role = user.roles[roleIndex];
        if (role.name === role_entity_1.SYSTEM_ROLES.SUPER_ADMIN) {
            const adminCount = await this.userRepository
                .createQueryBuilder('user')
                .innerJoin('user.roles', 'role')
                .where('role.name = :roleName', { roleName: role_entity_1.SYSTEM_ROLES.SUPER_ADMIN })
                .getCount();
            if (adminCount <= 1) {
                throw new exceptions_1.BadRequestException('Cannot remove last system administrator role');
            }
        }
        user.roles.splice(roleIndex, 1);
        await this.userRepository.save(user);
        await audit_service_1.auditService.log({
            userId: revokedBy,
            action: audit_log_entity_1.AuditAction.ROLE_REVOKE,
            resource: `user:${userId}`,
            description: `Revoked role ${role.name} from user`,
            metadata: { roleId, roleName: role.name },
            success: true,
        });
        return user;
    }
    async getUserPermissions(userId) {
        const user = await this.findById(userId);
        const permissions = new Map();
        user.roles.forEach(role => {
            role.permissions.forEach(permission => {
                permissions.set(permission.id, permission);
            });
        });
        return Array.from(permissions.values());
    }
    async getDefaultRoleForUserType(userType) {
        let roleName;
        switch (userType) {
            case user_entity_1.UserType.FARMER:
                roleName = role_entity_1.SYSTEM_ROLES.FARMER_BASIC;
                break;
            case user_entity_1.UserType.GOVERNMENT_OFFICIAL:
                roleName = role_entity_1.SYSTEM_ROLES.GOVERNMENT_OFFICIAL;
                break;
            case user_entity_1.UserType.ORGANIZATION:
                roleName = role_entity_1.SYSTEM_ROLES.ORGANIZATION_ADMIN;
                break;
            case user_entity_1.UserType.RESEARCHER:
                roleName = role_entity_1.SYSTEM_ROLES.RESEARCHER;
                break;
            case user_entity_1.UserType.SYSTEM_ADMIN:
                roleName = role_entity_1.SYSTEM_ROLES.SUPER_ADMIN;
                break;
            default:
                roleName = role_entity_1.SYSTEM_ROLES.GUEST;
        }
        return this.roleRepository.findOne({
            where: { name: roleName },
            relations: ['permissions'],
        });
    }
    async verifyEmail(userId) {
        const user = await this.findById(userId);
        user.emailVerified = true;
        user.emailVerifiedAt = new Date();
        await this.userRepository.save(user);
        return user;
    }
    async enable2FA(userId) {
        const user = await this.findById(userId);
        if (user.twoFactorEnabled) {
            throw new exceptions_1.BadRequestException('Two-factor authentication is already enabled');
        }
        await audit_service_1.auditService.log({
            userId,
            action: audit_log_entity_1.AuditAction.TWO_FACTOR_ENABLE,
            resource: `user:${userId}`,
            description: 'Two-factor authentication enable requested',
            success: true,
        });
    }
    async disable2FA(userId, disabledBy) {
        const user = await this.findById(userId);
        if (!user.twoFactorEnabled) {
            throw new exceptions_1.BadRequestException('Two-factor authentication is not enabled');
        }
        user.twoFactorEnabled = false;
        await this.userRepository.save(user);
        await audit_service_1.auditService.log({
            userId: disabledBy,
            action: audit_log_entity_1.AuditAction.TWO_FACTOR_DISABLE,
            resource: `user:${userId}`,
            description: 'Two-factor authentication disabled',
            success: true,
        });
    }
}
exports.userService = new UserService();
//# sourceMappingURL=user.service.js.map