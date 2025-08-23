import { Request, Response, NextFunction } from 'express';

/**
 * Wraps async route handlers to properly catch errors
 */
export const asyncHandler = (fn: Function) => (req: Request, res: Response, next: NextFunction) => {
  Promise.resolve(fn(req, res, next)).catch(next);
};