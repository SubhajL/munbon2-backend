const mockAuditLog = jest.fn();

const JWT = {
  secret: 'test-secret-that-is-at-least-32-bytes-long!!',
  issuer: 'munbon-auth',
  audience: 'munbon-services',
  accessTokenExpiresIn: '15m',
  refreshTokenExpiresIn: '7d',
};

jest.mock('../src/config/database', () => ({
  AppDataSource: {
    getRepository: jest.fn(() => ({})),
  },
}));

jest.mock('../src/config', () => ({
  config: {
    jwt: JWT,
    security: {
      maxLoginAttempts: 5,
      lockoutDuration: 15,
    },
  },
}));

jest.mock('../src/services/audit.service', () => ({
  auditService: {
    log: mockAuditLog,
  },
}));

jest.mock('../src/services/email.service', () => ({
  emailService: {},
}));

jest.mock('../src/services/user.service', () => ({
  userService: {},
}));

jest.mock('../src/utils/logger', () => ({
  logger: {
    info: jest.fn(),
    error: jest.fn(),
  },
}));

const { authService } = require('../src/services/auth.service');
const { RefreshToken } = require('../src/models/refresh-token.entity');
const { signAuthTokenPair } = require('../src/services/token-signer');

function createRefreshTokenRepository(user) {
  const tokens = new Map();

  return {
    tokens,
    create: jest.fn((values) =>
      Object.assign(new RefreshToken(), {
        isActive: true,
        user,
        ...values,
      }),
    ),
    save: jest.fn(async (token) => {
      tokens.set(token.token, token);
      return token;
    }),
    findOne: jest.fn(async ({ where }) => {
      const token = tokens.get(where.token) ?? null;
      if (token && where.userId && token.userId !== where.userId) {
        return null;
      }
      return token;
    }),
    update: jest.fn(async () => ({ affected: 0 })),
  };
}

describe('AuthService.logout', () => {
  const user = {
    id: 'operator-123',
    email: 'operator@munbon.test',
    roles: [{ name: 'operator' }],
    isLocked: () => false,
    failedLoginAttempts: 0,
    lockedUntil: null,
  };

  let refreshTokenRepository;

  beforeEach(() => {
    jest.clearAllMocks();
    refreshTokenRepository = createRefreshTokenRepository(user);
    authService.refreshTokenRepository = refreshTokenRepository;
    authService.userRepository = {
      findOne: jest.fn(),
      save: jest.fn(async (value) => value),
    };
    authService.loginAttemptRepository = {
      create: jest.fn((value) => ({ ...value })),
      save: jest.fn(async (value) => value),
    };
    jest.spyOn(authService, 'validateUser').mockResolvedValue(user);
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  test('login then rotation then logout rejects reuse of both submitted refresh tokens', async () => {
    const login = await authService.login(
      user.email,
      'valid-password',
      '127.0.0.1',
      'jest',
    );
    const rotated = await authService.refreshAccessToken(login.refreshToken);

    await expect(
      authService.refreshAccessToken(login.refreshToken),
    ).rejects.toMatchObject({
      statusCode: 401,
      message: 'Invalid refresh token',
    });

    await authService.logout(rotated.refreshToken);

    expect(
      refreshTokenRepository.tokens.get(rotated.refreshToken),
    ).toMatchObject({
      userId: user.id,
      isActive: false,
      revokedBy: user.id,
      revokeReason: 'User logout',
    });
    await expect(
      authService.refreshAccessToken(rotated.refreshToken),
    ).rejects.toMatchObject({
      statusCode: 401,
      message: 'Invalid refresh token',
    });
  });

  test('rejects a signed refresh token whose persisted owner does not match its subject', async () => {
    const { refreshToken } = signAuthTokenPair(
      {
        sub: 'different-operator',
        email: 'other@munbon.test',
        roles: ['operator'],
      },
      JWT,
    );
    const token = refreshTokenRepository.create({
      token: refreshToken,
      userId: user.id,
      expiresAt: new Date(Date.now() + 60_000),
    });
    await refreshTokenRepository.save(token);

    await expect(authService.logout(refreshToken)).rejects.toMatchObject({
      statusCode: 401,
      message: 'Invalid refresh token',
    });
    expect(token.isActive).toBe(true);
    expect(mockAuditLog).not.toHaveBeenCalled();
  });
});
