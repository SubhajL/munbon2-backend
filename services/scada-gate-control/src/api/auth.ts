/**
 * Authentication: verify JWT access tokens issued by `services/auth` and map
 * their role names to this app's Viewer/Operator/Admin roles.
 *
 * Tokens are HS256, signed with JWT_SECRET, with issuer/audience claims and a
 * `type: 'access'` discriminator. The token carries role NAMES only (no
 * permissions), so the mapping below is the authorization policy for gate
 * control — confirm the role-to-privilege mapping with RID before go-live.
 */
import jwt from 'jsonwebtoken';
import type { Role } from '../domain/write-safety';

export class AuthError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'AuthError';
  }
}

export type AuthenticatedUser = {
  readonly userId: string;
  readonly email: string;
  readonly roleNames: readonly string[];
  readonly role: Role;
};

export type RoleMapping = {
  readonly admin: readonly string[];
  readonly operator: readonly string[];
};

/** Default policy: RID admins manage; zone managers operate; everyone else reads. */
export const DEFAULT_ROLE_MAPPING: RoleMapping = {
  admin: ['super_admin', 'rid_admin'],
  operator: ['zone_manager'],
};

/** Highest privilege among the user's role names wins; unknown roles -> viewer. */
export function mapAppRole(
  roleNames: readonly string[],
  mapping: RoleMapping = DEFAULT_ROLE_MAPPING,
): Role {
  if (roleNames.some((name) => mapping.admin.includes(name))) return 'admin';
  if (roleNames.some((name) => mapping.operator.includes(name))) return 'operator';
  return 'viewer';
}

export interface TokenVerifier {
  verify(token: string): AuthenticatedUser;
}

export type JwtVerifierConfig = {
  readonly secret: string;
  readonly issuer: string;
  readonly audience: string;
  /** Reject tokens older than this regardless of exp (defaults to 15m). */
  readonly maxAge?: string;
  readonly roleMapping?: RoleMapping;
};

export class JwtTokenVerifier implements TokenVerifier {
  constructor(private readonly config: JwtVerifierConfig) {}

  verify(token: string): AuthenticatedUser {
    let payload: jwt.JwtPayload | string;
    try {
      payload = jwt.verify(token, this.config.secret, {
        issuer: this.config.issuer,
        audience: this.config.audience,
        algorithms: ['HS256'], // pin HS256 — no alg-confusion / 'none'
        maxAge: this.config.maxAge ?? '15m',
      });
    } catch {
      throw new AuthError('invalid or expired token');
    }
    if (typeof payload === 'string') {
      throw new AuthError('unexpected token payload');
    }
    if (typeof payload.exp !== 'number') {
      throw new AuthError('token missing expiry');
    }
    if (payload.type !== 'access') {
      throw new AuthError('not an access token');
    }
    if (typeof payload.sub !== 'string') {
      throw new AuthError('token missing subject');
    }
    const roleNames = Array.isArray(payload.roles)
      ? payload.roles.filter((name): name is string => typeof name === 'string')
      : [];
    return {
      userId: payload.sub,
      email: typeof payload.email === 'string' ? payload.email : '',
      roleNames,
      role: mapAppRole(roleNames, this.config.roleMapping),
    };
  }
}
