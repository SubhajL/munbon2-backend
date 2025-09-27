interface GenerateSecretResult {
    secret: string;
    qrCode: string;
    backupCodes: string[];
}
declare class TwoFactorService {
    private twoFactorSecretRepository;
    constructor();
    generateSecret(userId: string): Promise<GenerateSecretResult>;
    verifyAndEnable(userId: string, token: string): Promise<boolean>;
    verifyToken(userId: string, token: string): Promise<boolean>;
    disable(userId: string): Promise<void>;
    regenerateBackupCodes(userId: string): Promise<string[]>;
    isEnabled(userId: string): Promise<boolean>;
}
export declare const twoFactorService: TwoFactorService;
export {};
//# sourceMappingURL=two-factor.service.d.ts.map