import { Role } from './role.entity';
import { RefreshToken } from './refresh-token.entity';
import { LoginAttempt } from './login-attempt.entity';
import { AuditLog } from './audit-log.entity';
export declare enum UserStatus {
    ACTIVE = "active",
    INACTIVE = "inactive",
    LOCKED = "locked",
    SUSPENDED = "suspended"
}
export declare enum UserType {
    FARMER = "farmer",
    GOVERNMENT_OFFICIAL = "government_official",
    ORGANIZATION = "organization",
    RESEARCHER = "researcher",
    SYSTEM_ADMIN = "system_admin"
}
export declare class User {
    id: string;
    email: string;
    password: string;
    firstName: string;
    lastName: string;
    citizenId?: string;
    phoneNumber?: string;
    userType: UserType;
    status: UserStatus;
    emailVerified: boolean;
    emailVerifiedAt?: Date;
    twoFactorEnabled: boolean;
    thaiDigitalId?: string;
    profileImage?: string;
    metadata?: Record<string, any>;
    lastLoginAt?: Date;
    lastLoginIp?: string;
    failedLoginAttempts: number;
    lockedUntil?: Date;
    organizationId?: string;
    zoneId?: string;
    roles: Role[];
    refreshTokens: RefreshToken[];
    loginAttempts: LoginAttempt[];
    auditLogs: AuditLog[];
    createdAt: Date;
    updatedAt: Date;
    hashPassword(): Promise<void>;
    comparePassword(password: string): Promise<boolean>;
    hasRole(roleName: string): boolean;
    hasPermission(permissionName: string): boolean;
    isLocked(): boolean;
    toJSON(): Omit<this, "password" | "hashPassword" | "comparePassword" | "hasRole" | "hasPermission" | "isLocked" | "toJSON">;
}
//# sourceMappingURL=user.entity.d.ts.map