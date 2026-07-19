const jwt = require('jsonwebtoken');
const { signAuthTokenPair } = require('../src/services/token-signer');

// A >=32-byte secret so jwt.verify has no objection. issuer/audience here are
// REPRESENTATIVE fixtures — the unit test signs and verifies with the same
// values. In deployment, auth's JWT_ISSUER/JWT_AUDIENCE must equal the
// scheduler's jwt_issuer/jwt_audience (the PM2 contract uses "munbon-scheduler")
// or the scheduler rejects a present-but-mismatched audience in compat AND strict.
const JWT = {
  secret: 'test-secret-that-is-at-least-32-bytes-long!!',
  issuer: 'munbon-auth',
  audience: 'munbon-services',
  accessTokenExpiresIn: '15m',
  refreshTokenExpiresIn: '7d',
};
const principal = { sub: 'user-123', email: 'op@munbon.test', roles: ['operator'] };

describe('signAuthTokenPair', () => {
  test('access token carries a non-blank jti plus iss/aud/type/roles/sub', () => {
    const { accessToken } = signAuthTokenPair(principal, JWT);
    const decoded = jwt.verify(accessToken, JWT.secret, {
      issuer: JWT.issuer,
      audience: JWT.audience,
    });
    expect(typeof decoded.jti).toBe('string');
    expect(decoded.jti.length).toBeGreaterThan(0);
    expect(decoded.iss).toBe('munbon-auth');
    expect(decoded.aud).toBe('munbon-services');
    expect(decoded.type).toBe('access');
    expect(decoded.roles).toEqual(['operator']);
    expect(decoded.sub).toBe('user-123');
  });

  test('access and refresh tokens receive DISTINCT jti values', () => {
    const { accessToken, refreshToken } = signAuthTokenPair(principal, JWT);
    const a = jwt.decode(accessToken);
    const r = jwt.decode(refreshToken);
    expect(a.jti).toEqual(expect.any(String));
    expect(r.jti).toEqual(expect.any(String));
    expect(a.jti).not.toBe(r.jti);
    expect(a.type).toBe('access');
    expect(r.type).toBe('refresh');
  });

  test('the jti generator is injectable (deterministic for tests)', () => {
    let n = 0;
    const { accessToken, refreshToken } = signAuthTokenPair(
      principal,
      JWT,
      () => `fixed-jti-${n++}`
    );
    expect(jwt.decode(accessToken).jti).toBe('fixed-jti-0');
    expect(jwt.decode(refreshToken).jti).toBe('fixed-jti-1');
  });

  test('expiresIn is the access-token lifetime in seconds', () => {
    const { expiresIn } = signAuthTokenPair(principal, JWT);
    expect(expiresIn).toBe(15 * 60);
  });

  test('each token gets its OWN lifetime (access=15m, refresh=7d)', () => {
    // Guards against a future edit that swaps the two expiresIn options between
    // the access and refresh sign calls (which the returned-expiresIn check
    // above cannot catch, since it is a hardcoded constant).
    const { accessToken, refreshToken } = signAuthTokenPair(principal, JWT);
    const a = jwt.decode(accessToken);
    const r = jwt.decode(refreshToken);
    expect(a.exp - a.iat).toBe(15 * 60); // 15m
    expect(r.exp - r.iat).toBe(7 * 24 * 60 * 60); // 7d
  });

  test('two separate calls (logins) produce DISTINCT jti values', () => {
    const first = jwt.decode(signAuthTokenPair(principal, JWT).accessToken);
    const second = jwt.decode(signAuthTokenPair(principal, JWT).accessToken);
    expect(first.jti).not.toBe(second.jti);
  });
});
