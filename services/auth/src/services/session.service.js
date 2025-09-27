"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.sessionService = void 0;
const database_1 = require("../config/database");
const session_entity_1 = require("../models/session.entity");
const refresh_token_entity_1 = require("../models/refresh-token.entity");
class SessionService {
    sessionRepository;
    refreshTokenRepository;
    constructor() {
        this.sessionRepository = database_1.AppDataSource.getRepository(session_entity_1.Session);
        this.refreshTokenRepository = database_1.AppDataSource.getRepository(refresh_token_entity_1.RefreshToken);
    }
    async getUserSessions(userId) {
        const refreshTokens = await this.refreshTokenRepository.find({
            where: { userId, isActive: true },
            order: { createdAt: 'DESC' },
        });
        return refreshTokens.map(token => ({
            id: token.id,
            deviceName: token.deviceName || 'Unknown Device',
            userAgent: token.userAgent,
            ip: token.ip,
            createdAt: token.createdAt,
            lastUsed: token.createdAt,
            current: false,
        }));
    }
    async revokeSession(sessionId, userId) {
        await this.refreshTokenRepository.update({ id: sessionId, userId }, { isActive: false, revokedAt: new Date(), revokedBy: userId });
    }
}
exports.sessionService = new SessionService();
//# sourceMappingURL=session.service.js.map