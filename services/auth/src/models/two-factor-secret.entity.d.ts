import { User } from './user.entity';
export declare class TwoFactorSecret {
    id: string;
    userId: string;
    user: User;
    secret: string;
    backupCodes: string[];
    usedBackupCodes: string[];
    verified: boolean;
    verifiedAt?: Date;
    lastUsedAt?: Date;
    createdAt: Date;
    updatedAt: Date;
    useBackupCode(code: string): boolean;
    hasUnusedBackupCodes(): boolean;
}
//# sourceMappingURL=two-factor-secret.entity.d.ts.map