import { Request, Response, NextFunction } from 'express';
import Joi from 'joi';
import { logger } from '@utils/logger';

export function validateRequest(schema: {
  body?: Joi.Schema;
  query?: Joi.Schema;
  params?: Joi.Schema;
}) {
  return (req: Request, res: Response, next: NextFunction) => {
    const errors: string[] = [];

    // Validate body
    if (schema.body) {
      const { error } = schema.body.validate(req.body);
      if (error) {
        errors.push(...error.details.map(detail => detail.message));
      }
    }

    // Validate query
    if (schema.query) {
      const { error } = schema.query.validate(req.query);
      if (error) {
        errors.push(...error.details.map(detail => detail.message));
      }
    }

    // Validate params
    if (schema.params) {
      const { error } = schema.params.validate(req.params);
      if (error) {
        errors.push(...error.details.map(detail => detail.message));
      }
    }

    if (errors.length > 0) {
      logger.warn('Validation error', { errors, url: req.url });
      res.status(400).json({
        success: false,
        message: 'Validation error',
        errors,
      });
      return;
    }

    next();
  };
}