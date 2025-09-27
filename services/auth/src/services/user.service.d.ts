import { User, UserStatus, UserType } from '../models/user.entity';
import { Role } from '../models/role.entity';
import { Permission } from '../models/permission.entity';
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
declare class UserService {
    private userRepository;
    private roleRepository;
    private permissionRepository;
    constructor();
    findById(id: string): Promise<User>;
    findByEmail(email: string): Promise<User | null>;
    findByCitizenId(citizenId: string): Promise<User | null>;
    findAll(filter: UserFilter, pagination: PaginationOptions): Promise<PaginatedResponse<User>>;
    update(id: string, data: UpdateUserData, updatedBy: string): Promise<User>;
    updateStatus(id: string, status: UserStatus, updatedBy: string, reason?: string): Promise<User>;
    delete(id: string, deletedBy: string): Promise<void>;
    assignRole(userId: string, roleId: string, assignedBy: string): Promise<User>;
    revokeRole(userId: string, roleId: string, revokedBy: string): Promise<User>;
    getUserPermissions(userId: string): Promise<Permission[]>;
    getDefaultRoleForUserType(userType: UserType): Promise<Role | null>;
    verifyEmail(userId: string): Promise<User>;
    enable2FA(userId: string): Promise<void>;
    disable2FA(userId: string, disabledBy: string): Promise<void>;
}
export declare const userService: UserService;
export {};
//# sourceMappingURL=user.service.d.ts.map