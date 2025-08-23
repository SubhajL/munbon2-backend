import { Request, Response, NextFunction } from 'express';

type AsyncFunction = (
  req: Request,
  res: Response,
  next: NextFunction
) => Promise<any>;

/**
 * Wraps async route handlers to properly catch errors
 */
export const asyncHandler = (fn: AsyncFunction) => {
  return (req: Request, res: Response, next: NextFunction) => {
    Promise.resolve(fn(req, res, next)).catch(next);
  };
};