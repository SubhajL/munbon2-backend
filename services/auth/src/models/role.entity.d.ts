import { User } from './user.entity';
import { Permission } from './permission.entity';
export declare class Role {
    id: string;
    name: string;
    displayName: string;
    description?: string;
    isActive: boolean;
    isSystem: boolean;
    metadata?: Record<string, any>;
    users: User[];
    permissions: Permission[];
    createdAt: Date;
    updatedAt: Date;
    hasPermission(permissionName: string): boolean;
}
export declare const SYSTEM_ROLES: {
    readonly SUPER_ADMIN: "super_admin";
    readonly RID_ADMIN: "rid_admin";
    readonly ZONE_MANAGER: "zone_manager";
    readonly GOVERNMENT_OFFICIAL: "government_official";
    readonly ORGANIZATION_ADMIN: "organization_admin";
    readonly FARMER_PREMIUM: "farmer_premium";
    readonly FARMER_BASIC: "farmer_basic";
    readonly RESEARCHER: "researcher";
    readonly GUEST: "guest";
};
//# sourceMappingURL=role.entity.d.ts.map