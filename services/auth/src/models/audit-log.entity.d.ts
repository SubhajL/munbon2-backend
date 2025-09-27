import { User } from './user.entity';
export declare enum AuditAction {
    LOGIN = "login",
    LOGOUT = "logout",
    LOGIN_FAILED = "login_failed",
    TOKEN_REFRESH = "token_refresh",
    PASSWORD_RESET_REQUEST = "password_reset_request",
    PASSWORD_RESET_COMPLETE = "password_reset_complete",
    USER_CREATE = "user_create",
    USER_UPDATE = "user_update",
    USER_DELETE = "user_delete",
    USER_LOCK = "user_lock",
    USER_UNLOCK = "user_unlock",
    ROLE_ASSIGN = "role_assign",
    ROLE_REVOKE = "role_revoke",
    PERMISSION_GRANT = "permission_grant",
    PERMISSION_REVOKE = "permission_revoke",
    TWO_FACTOR_ENABLE = "two_factor_enable",
    TWO_FACTOR_DISABLE = "two_factor_disable",
    TWO_FACTOR_VERIFY = "two_factor_verify",
    SUSPICIOUS_ACTIVITY = "suspicious_activity",
    ACCESS_DENIED = "access_denied"
}
export declare class AuditLog {
    id: string;
    userId?: string;
    user?: User;
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
    createdAt: Date;
}
//# sourceMappingURL=audit-log.entity.d.ts.map