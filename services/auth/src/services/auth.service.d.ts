import { User } from '../models/user.entity';
interface LoginResult {
    user: User;
    accessToken: string;
    refreshToken: string;
    expiresIn: number;
    tokenType: string;
}
interface RegisterData {
    email: string;
    password: string;
    firstName: string;
    lastName: string;
    citizenId?: string;
    phoneNumber?: string;
    userType?: string;
    organizationId?: string;
    zoneId?: string;
}
declare class AuthService {
    private userRepository;
    private refreshTokenRepository;
    private loginAttemptRepository;
    private passwordResetRepository;
    constructor();
    register(data: RegisterData): Promise<User>;
    login(email: string, password: string, ip: string, userAgent?: string): Promise<LoginResult>;
    validateUser(email: string, password: string): Promise<User | null>;
    refreshAccessToken(refreshToken: string): Promise<LoginResult>;
    logout(refreshToken: string): Promise<void>;
    requestPasswordReset(email: string, ip: string): Promise<void>;
    resetPassword(token: string, newPassword: string, ip: string): Promise<void>;
    getThaiDigitalIdUserInfo(accessToken: string): Promise<any>;
    findOrCreateFromThaiDigitalId(userInfo: any): Promise<User>;
    private generateTokens;
}
export declare const authService: AuthService;
export {};
//# sourceMappingURL=auth.service.d.ts.map
