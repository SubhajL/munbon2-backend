import { Repository } from 'typeorm';
import { AppDataSource } from '../config/database';
import { Session } from '../models/session.entity';
import { RefreshToken } from '../models/refresh-token.entity';

class SessionService {
  private sessionRepository: Repository<Session>;
  private refreshTokenRepository: Repository<RefreshToken>;

  constructor() {
    this.sessionRepository = AppDataSource.getRepository(Session);
    this.refreshTokenRepository = AppDataSource.getRepository(RefreshToken);
  }

  async getUserSessions(userId: string): Promise<any[]> {
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
      lastUsed: token.createdAt, // TODO: Track last used
      current: false, // TODO: Identify current session
    }));
  }

  async revokeSession(sessionId: string, userId: string): Promise<void> {
    await this.refreshTokenRepository.update(
      { id: sessionId, userId },
      { isActive: false, revokedAt: new Date(), revokedBy: userId }
    );
  }
}

export const sessionService = new SessionService();