import jwt from 'jsonwebtoken';
import type { SignOptions } from 'jsonwebtoken';
import { randomUUID } from 'crypto';

export interface TokenPrincipal {
  sub: string;
  email: string;
  roles: string[];
}

export interface JwtSigningConfig {
  secret: string;
  issuer: string;
  audience: string;
  // Use jsonwebtoken's own expiry type (string | number) so this compiles
  // under @types/jsonwebtoken@9 (a bare `string` is not assignable there).
  accessTokenExpiresIn: SignOptions['expiresIn'];
  refreshTokenExpiresIn: SignOptions['expiresIn'];
}

export interface SignedTokenPair {
  accessToken: string;
  refreshToken: string;
  expiresIn: number;
}

// Signs the access + refresh token pair for `principal`, embedding a UNIQUE jti
// per token (via jsonwebtoken's `jwtid`). The jti is what lets the scheduler's
// fail-closed revocation identify/revoke an individual token and is REQUIRED by
// its strict claim policy (services/scheduler core/auth.validate_access_token_claims:
// iss/aud/type/jti/roles). `makeJti` is injectable so tests are deterministic;
// it defaults to a random UUID v4 and MUST yield a fresh, non-blank id on each
// call — reusing one would give both tokens the same revocation identity.
export function signAuthTokenPair(
  principal: TokenPrincipal,
  jwtConfig: JwtSigningConfig,
  makeJti: () => string = randomUUID
): SignedTokenPair {
  const base = {
    sub: principal.sub,
    email: principal.email,
    roles: principal.roles,
  };
  const accessToken = jwt.sign({ ...base, type: 'access' }, jwtConfig.secret, {
    expiresIn: jwtConfig.accessTokenExpiresIn,
    issuer: jwtConfig.issuer,
    audience: jwtConfig.audience,
    jwtid: makeJti(),
  });
  const refreshToken = jwt.sign({ ...base, type: 'refresh' }, jwtConfig.secret, {
    expiresIn: jwtConfig.refreshTokenExpiresIn,
    issuer: jwtConfig.issuer,
    audience: jwtConfig.audience,
    jwtid: makeJti(),
  });
  // 15 minutes, matching the access-token lifetime advertised to clients.
  const expiresIn = 15 * 60;
  return { accessToken, refreshToken, expiresIn };
}
