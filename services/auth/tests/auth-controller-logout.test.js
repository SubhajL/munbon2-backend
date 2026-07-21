jest.mock('../src/services/auth.service', () => ({
  authService: {
    logout: jest.fn(),
  },
}));

jest.mock('../src/services/two-factor.service', () => ({
  twoFactorService: {},
}));

jest.mock('../src/services/session.service', () => ({
  sessionService: {},
}));

const { authController } = require('../src/controllers/auth.controller');
const { authService } = require('../src/services/auth.service');

describe('AuthController.logout', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('revokes the submitted refresh token without an access-token user', async () => {
    const refreshToken = 'submitted-refresh-token';
    const req = {
      body: { refreshToken },
      cookies: {},
    };
    const res = {
      clearCookie: jest.fn(),
      json: jest.fn(),
    };
    const next = jest.fn();

    await authController.logout(req, res, next);

    expect(authService.logout).toHaveBeenCalledWith(refreshToken);
    expect(res.clearCookie).toHaveBeenCalledWith('refreshToken');
    expect(res.json).toHaveBeenCalledWith({
      success: true,
      message: 'Logged out successfully',
    });
    expect(next).not.toHaveBeenCalled();
  });

  test('clears the refresh cookie when submitted-token revocation is rejected', async () => {
    const rejection = new Error('invalid refresh token');
    authService.logout.mockRejectedValueOnce(rejection);
    const req = {
      body: { refreshToken: 'invalid-refresh-token' },
      cookies: {},
    };
    const res = {
      clearCookie: jest.fn(),
      json: jest.fn(),
    };
    const next = jest.fn();

    await authController.logout(req, res, next);

    expect(res.clearCookie).toHaveBeenCalledWith('refreshToken');
    expect(next).toHaveBeenCalledWith(rejection);
    expect(res.json).not.toHaveBeenCalled();
  });
});
