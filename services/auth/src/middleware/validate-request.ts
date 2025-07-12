import { Request, Response, NextFunction } from 'express';
import Joi from 'joi';
import { ValidationException } from '../utils/exceptions';

export const validateRequest = (schema: Joi.ObjectSchema) => {
  return (req: Request, res: Response, next: NextFunction) => {
    const { error, value } = schema.validate(req.body, {
      abortEarly: false,
      stripUnknown: true,
    });

    if (error) {
      throw new ValidationException('Validation failed', error.details);
    }

    req.body = value;
    next();
  };
};