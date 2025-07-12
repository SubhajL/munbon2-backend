import { Request, Response, NextFunction } from 'express';
import { ApiError } from '../utils/api-error';

export const authorize = (allowedRoles: string[]) => {
  return (req: Request, res: Response, next: NextFunction): void => {
    if (!req.user) {
      next(new ApiError(401, 'Authentication required'));
      return;
    }

    const userRoles = req.user.roles || [];
    const hasPermission = userRoles.some(role => allowedRoles.includes(role));

    if (!hasPermission) {
      next(new ApiError(403, 'Insufficient permissions'));
      return;
    }

    next();
  };
};