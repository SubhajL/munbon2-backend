import { Request, Response, NextFunction } from 'express';
import { ZodSchema } from 'zod';
import { ApiError } from '../utils/api-error';

export const validateRequest = (schema: ZodSchema) => {
  return async (req: Request, res: Response, next: NextFunction) => {
    try {
      await schema.parseAsync({
        body: req.body,
        query: req.query,
        params: req.params,
      });
      next();
    } catch (error: any) {
      const errorMessage = error.errors?.map((e: any) => ({
        field: e.path.join('.'),
        message: e.message,
      }));
      next(new ApiError(400, 'Validation error', errorMessage));
    }
  };
};