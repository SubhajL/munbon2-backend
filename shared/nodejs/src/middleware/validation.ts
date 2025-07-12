import { Request, Response, NextFunction } from 'express';
import joi from 'joi';
import { ValidationError } from '../errors';

type ValidationTarget = 'body' | 'query' | 'params' | 'headers';

export interface ValidationOptions {
  abortEarly?: boolean;
  stripUnknown?: boolean;
  target?: ValidationTarget;
}

export const validate = (
  schema: joi.Schema,
  options: ValidationOptions = {}
) => {
  const {
    abortEarly = false,
    stripUnknown = true,
    target = 'body'
  } = options;

  return (req: Request, _res: Response, next: NextFunction): void => {
    const data = req[target];
    
    const { error, value } = schema.validate(data, {
      abortEarly,
      stripUnknown
    });

    if (error) {
      const errors: Record<string, string> = {};
      error.details.forEach(detail => {
        const key = detail.path.join('.');
        errors[key] = detail.message;
      });

      return next(new ValidationError('Validation failed', errors));
    }

    // Replace with validated value
    req[target] = value;
    next();
  };
};