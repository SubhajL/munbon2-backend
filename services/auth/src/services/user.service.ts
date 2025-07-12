import { Repository, FindOptionsWhere, ILike } from 'typeorm';
import { AppDataSource } from '../config/database';
import { User, UserStatus, UserType } from '../models/user.entity';
import { Role, SYSTEM_ROLES } from '../models/role.entity';
import { Permission } from '../models/permission.entity';
import { auditService } from './audit.service';
import { AuditAction } from '../models/audit-log.entity';
import { NotFoundException, BadRequestException, ConflictException } from '../utils/exceptions';
import { PaginatedResponse, PaginationOptions } from '../types';

interface UpdateUserData {
  firstName?: string;
  lastName?: string;
  phoneNumber?: string;
  userType?: UserType;
  organizationId?: string;
  zoneId?: string;
  metadata?: Record<string, any>;
}

interface UserFilter {
  status?: UserStatus;
  userType?: UserType;
  organizationId?: string;
  zoneId?: string;
  roleId?: string;
  search?: string;
}

class UserService {
  private userRepository: Repository<User>;
  private roleRepository: Repository<Role>;
  private permissionRepository: Repository<Permission>;

  constructor() {
    this.userRepository = AppDataSource.getRepository(User);
    this.roleRepository = AppDataSource.getRepository(Role);
    this.permissionRepository = AppDataSource.getRepository(Permission);
  }

  async findById(id: string): Promise<User> {
    const user = await this.userRepository.findOne({
      where: { id },
      relations: ['roles', 'roles.permissions'],
    });

    if (!user) {
      throw new NotFoundException('User not found');
    }

    return user;
  }

  async findByEmail(email: string): Promise<User | null> {
    return this.userRepository.findOne({
      where: { email },
      relations: ['roles', 'roles.permissions'],
    });
  }

  async findByCitizenId(citizenId: string): Promise<User | null> {
    return this.userRepository.findOne({
      where: { citizenId },
      relations: ['roles', 'roles.permissions'],
    });
  }

  async findAll(
    filter: UserFilter,
    pagination: PaginationOptions
  ): Promise<PaginatedResponse<User>> {
    const where: FindOptionsWhere<User> = {};

    if (filter.status) where.status = filter.status;
    if (filter.userType) where.userType = filter.userType;
    if (filter.organizationId) where.organizationId = filter.organizationId;
    if (filter.zoneId) where.zoneId = filter.zoneId;

    // Handle search
    const searchConditions = [];
    if (filter.search) {
      searchConditions.push(
        { email: ILike(`%${filter.search}%`) },
        { firstName: ILike(`%${filter.search}%`) },
        { lastName: ILike(`%${filter.search}%`) },
        { citizenId: ILike(`%${filter.search}%`) },
        { phoneNumber: ILike(`%${filter.search}%`) }
      );
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

    // Filter by role if specified
    let filteredUsers = users;
    if (filter.roleId) {
      filteredUsers = users.filter(user =>
        user.roles.some(role => role.id === filter.roleId)
      );
    }

    return {
      data: filteredUsers,
      total,
      page: pagination.page,
      limit: pagination.limit,
      totalPages: Math.ceil(total / pagination.limit),
    };
  }

  async update(
    id: string,
    data: UpdateUserData,
    updatedBy: string
  ): Promise<User> {
    const user = await this.findById(id);

    // Check for conflicts
    if (data.phoneNumber && data.phoneNumber !== user.phoneNumber) {
      const existing = await this.userRepository.findOne({
        where: { phoneNumber: data.phoneNumber },
      });
      if (existing) {
        throw new ConflictException('Phone number already in use');
      }
    }

    // Store old values for audit
    const oldValues = {
      firstName: user.firstName,
      lastName: user.lastName,
      phoneNumber: user.phoneNumber,
      userType: user.userType,
      organizationId: user.organizationId,
      zoneId: user.zoneId,
    };

    // Update user
    Object.assign(user, data);
    await this.userRepository.save(user);

    // Audit log
    await auditService.log({
      userId: updatedBy,
      action: AuditAction.USER_UPDATE,
      resource: `user:${id}`,
      description: 'User updated',
      oldValues,
      newValues: data,
      success: true,
    });

    return user;
  }

  async updateStatus(
    id: string,
    status: UserStatus,
    updatedBy: string,
    reason?: string
  ): Promise<User> {
    const user = await this.findById(id);
    const oldStatus = user.status;

    user.status = status;
    if (status === UserStatus.LOCKED) {
      user.lockedUntil = new Date(Date.now() + 24 * 60 * 60 * 1000); // 24 hours
    } else {
      user.lockedUntil = null;
      user.failedLoginAttempts = 0;
    }

    await this.userRepository.save(user);

    // Determine audit action
    let action: AuditAction;
    if (status === UserStatus.LOCKED) {
      action = AuditAction.USER_LOCK;
    } else if (oldStatus === UserStatus.LOCKED && status === UserStatus.ACTIVE) {
      action = AuditAction.USER_UNLOCK;
    } else {
      action = AuditAction.USER_UPDATE;
    }

    // Audit log
    await auditService.log({
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

  async delete(id: string, deletedBy: string): Promise<void> {
    const user = await this.findById(id);

    // Prevent deletion of system users
    if (user.hasRole(SYSTEM_ROLES.SUPER_ADMIN)) {
      throw new BadRequestException('Cannot delete system administrator');
    }

    await this.userRepository.remove(user);

    // Audit log
    await auditService.log({
      userId: deletedBy,
      action: AuditAction.USER_DELETE,
      resource: `user:${id}`,
      description: 'User deleted',
      metadata: { deletedUser: user.email },
      success: true,
    });
  }

  async assignRole(
    userId: string,
    roleId: string,
    assignedBy: string
  ): Promise<User> {
    const user = await this.findById(userId);
    const role = await this.roleRepository.findOne({
      where: { id: roleId },
      relations: ['permissions'],
    });

    if (!role) {
      throw new NotFoundException('Role not found');
    }

    // Check if user already has the role
    if (user.roles.some(r => r.id === roleId)) {
      throw new ConflictException('User already has this role');
    }

    user.roles.push(role);
    await this.userRepository.save(user);

    // Audit log
    await auditService.log({
      userId: assignedBy,
      action: AuditAction.ROLE_ASSIGN,
      resource: `user:${userId}`,
      description: `Assigned role ${role.name} to user`,
      metadata: { roleId, roleName: role.name },
      success: true,
    });

    return user;
  }

  async revokeRole(
    userId: string,
    roleId: string,
    revokedBy: string
  ): Promise<User> {
    const user = await this.findById(userId);

    // Check if user has the role
    const roleIndex = user.roles.findIndex(r => r.id === roleId);
    if (roleIndex === -1) {
      throw new BadRequestException('User does not have this role');
    }

    const role = user.roles[roleIndex];

    // Prevent removing last admin role
    if (role.name === SYSTEM_ROLES.SUPER_ADMIN) {
      const adminCount = await this.userRepository
        .createQueryBuilder('user')
        .innerJoin('user.roles', 'role')
        .where('role.name = :roleName', { roleName: SYSTEM_ROLES.SUPER_ADMIN })
        .getCount();

      if (adminCount <= 1) {
        throw new BadRequestException('Cannot remove last system administrator role');
      }
    }

    user.roles.splice(roleIndex, 1);
    await this.userRepository.save(user);

    // Audit log
    await auditService.log({
      userId: revokedBy,
      action: AuditAction.ROLE_REVOKE,
      resource: `user:${userId}`,
      description: `Revoked role ${role.name} from user`,
      metadata: { roleId, roleName: role.name },
      success: true,
    });

    return user;
  }

  async getUserPermissions(userId: string): Promise<Permission[]> {
    const user = await this.findById(userId);
    const permissions = new Map<string, Permission>();

    // Collect all unique permissions from user's roles
    user.roles.forEach(role => {
      role.permissions.forEach(permission => {
        permissions.set(permission.id, permission);
      });
    });

    return Array.from(permissions.values());
  }

  async getDefaultRoleForUserType(userType: UserType): Promise<Role | null> {
    let roleName: string;

    switch (userType) {
      case UserType.FARMER:
        roleName = SYSTEM_ROLES.FARMER_BASIC;
        break;
      case UserType.GOVERNMENT_OFFICIAL:
        roleName = SYSTEM_ROLES.GOVERNMENT_OFFICIAL;
        break;
      case UserType.ORGANIZATION:
        roleName = SYSTEM_ROLES.ORGANIZATION_ADMIN;
        break;
      case UserType.RESEARCHER:
        roleName = SYSTEM_ROLES.RESEARCHER;
        break;
      case UserType.SYSTEM_ADMIN:
        roleName = SYSTEM_ROLES.SUPER_ADMIN;
        break;
      default:
        roleName = SYSTEM_ROLES.GUEST;
    }

    return this.roleRepository.findOne({
      where: { name: roleName },
      relations: ['permissions'],
    });
  }

  async verifyEmail(userId: string): Promise<User> {
    const user = await this.findById(userId);

    user.emailVerified = true;
    user.emailVerifiedAt = new Date();
    await this.userRepository.save(user);

    return user;
  }

  async enable2FA(userId: string): Promise<void> {
    const user = await this.findById(userId);

    if (user.twoFactorEnabled) {
      throw new BadRequestException('Two-factor authentication is already enabled');
    }

    // This will be handled by two-factor service
    // Just marking the intent here
    await auditService.log({
      userId,
      action: AuditAction.TWO_FACTOR_ENABLE,
      resource: `user:${userId}`,
      description: 'Two-factor authentication enable requested',
      success: true,
    });
  }

  async disable2FA(userId: string, disabledBy: string): Promise<void> {
    const user = await this.findById(userId);

    if (!user.twoFactorEnabled) {
      throw new BadRequestException('Two-factor authentication is not enabled');
    }

    user.twoFactorEnabled = false;
    await this.userRepository.save(user);

    await auditService.log({
      userId: disabledBy,
      action: AuditAction.TWO_FACTOR_DISABLE,
      resource: `user:${userId}`,
      description: 'Two-factor authentication disabled',
      success: true,
    });
  }
}

export const userService = new UserService();