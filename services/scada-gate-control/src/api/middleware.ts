import type { NextFunction, Request, Response } from 'express';
import { AuthError, type AuthenticatedUser, type TokenVerifier } from './auth';

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
