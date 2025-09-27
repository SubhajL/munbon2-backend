declare class SessionService {
    private sessionRepository;
    private refreshTokenRepository;
    constructor();
    getUserSessions(userId: string): Promise<any[]>;
    revokeSession(sessionId: string, userId: string): Promise<void>;
}
export declare const sessionService: SessionService;
export {};
//# sourceMappingURL=session.service.d.ts.map