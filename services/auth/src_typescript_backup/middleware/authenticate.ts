import { Request, Response, NextFunction } from 'express';
import passport from 'passport';
import { UnauthorizedException } from '../utils/exceptions';

export interface AuthenticatedRequest extends Request {
  user?: any;
}

export const authenticate = (req: Request, res: Response, next: NextFunction) => {
  passport.authenticate('jwt', { session: false }, (err: Error, user: any, info: any) => {
    if (err) {
      return next(err);
    }

    if (!user) {
      throw new UnauthorizedException(info?.message || 'Authentication required');
    }

    req.user = user;
    next();
  })(req, res, next);
};

export const authenticateOptional = (req: Request, res: Response, next: NextFunction) => {
  passport.authenticate('jwt', { session: false }, (err: Error, user: any) => {
    if (err) {
      return next(err);
    }

    req.user = user || null;
    next();
  })(req, res, next);
};