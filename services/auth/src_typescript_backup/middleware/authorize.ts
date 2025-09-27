import { Request, Response, NextFunction } from 'express';
import { ForbiddenException } from '../utils/exceptions';

export const authorize = (...permissions: string[]) => {
  return (req: Request, res: Response, next: NextFunction) => {
    if (!req.user) {
      throw new ForbiddenException('User not authenticated');
    }

    const hasPermission = permissions.some(permission => 
      req.user.hasPermission(permission)
    );

    if (!hasPermission) {
      throw new ForbiddenException('Insufficient permissions');
    }

    next();
  };
};

export const authorizeRoles = (...roles: string[]) => {
  return (req: Request, res: Response, next: NextFunction) => {
    if (!req.user) {
      throw new ForbiddenException('User not authenticated');
    }

    const hasRole = roles.some(role => 
      req.user.hasRole(role)
    );

    if (!hasRole) {
      throw new ForbiddenException('Insufficient role privileges');
    }

    next();
  };
};