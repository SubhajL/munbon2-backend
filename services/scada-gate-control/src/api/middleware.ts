import type { NextFunction, Request, Response } from 'express';
import { AuthError, type AuthenticatedUser, type TokenVerifier } from './auth';
import type { Role } from '../domain/write-safety';

declare global {
  // eslint-disable-next-line @typescript-eslint/no-namespace
  namespace Express {
    interface Request {
      auth?: AuthenticatedUser;
    }
  }
}

/** Express middleware: require a valid Bearer access token; attaches req.auth. */
export function requireAuth(verifier: TokenVerifier) {
  return (req: Request, res: Response, next: NextFunction): void => {
    const header = req.header('authorization') ?? '';
    const match = /^Bearer (.+)$/i.exec(header);
    const token = match?.[1];
    if (!token) {
      res.status(401).json({ error: 'missing bearer token' });
      return;
    }
    try {
      req.auth = verifier.verify(token);
      next();
    } catch (error) {
      if (error instanceof AuthError) {
        res.status(401).json({ error: error.message });
        return;
      }
      next(error);
    }
  };
}

const ROLE_RANK: Record<Role, number> = { viewer: 0, operator: 1, admin: 2 };

/**
 * Express middleware: require the authenticated user's mapped app role to be at
 * least `minRole` (viewer < operator < admin). MUST run AFTER `requireAuth`, which
 * populates `req.auth`. Responds 403 for an authenticated-but-under-privileged
 * caller; missing `req.auth` also 403s (defense-in-depth if mis-wired).
 */
export function requireRole(minRole: Role) {
  return (req: Request, res: Response, next: NextFunction): void => {
    const role = req.auth?.role;
    if (role === undefined || ROLE_RANK[role] < ROLE_RANK[minRole]) {
      res.status(403).json({ error: `requires ${minRole} role or higher` });
      return;
    }
    next();
  };
}
