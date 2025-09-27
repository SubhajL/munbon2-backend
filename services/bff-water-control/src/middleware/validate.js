const Joi = require('joi');
const { logger } = require('../utils/logger');

/**
 * Validation middleware factory
 * @param {Object} schemas - Object containing validation schemas for different request parts
 * @param {Joi.Schema} schemas.body - Schema for request body
 * @param {Joi.Schema} schemas.query - Schema for query parameters
 * @param {Joi.Schema} schemas.params - Schema for route parameters
 */
const validateRequest = (schemas) => {
  return (req, res, next) => {
    const validationErrors = [];

    // Validate body
    if (schemas.body) {
      const { error, value } = schemas.body.validate(req.body, { abortEarly: false });
      if (error) {
        validationErrors.push(...error.details.map(detail => ({
          field: detail.path.join('.'),
          message: detail.message,
          type: 'body'
        })));
      } else {
        req.body = value; // Use validated and sanitized value
      }
    }

    // Validate query parameters
    if (schemas.query) {
      const { error, value } = schemas.query.validate(req.query, { abortEarly: false });
      if (error) {
        validationErrors.push(...error.details.map(detail => ({
          field: detail.path.join('.'),
          message: detail.message,
          type: 'query'
        })));
      } else {
        req.query = value;
      }
    }

    // Validate route parameters
    if (schemas.params) {
      const { error, value } = schemas.params.validate(req.params, { abortEarly: false });
      if (error) {
        validationErrors.push(...error.details.map(detail => ({
          field: detail.path.join('.'),
          message: detail.message,
          type: 'params'
        })));
      } else {
        req.params = value;
      }
    }

    // Check if there are any validation errors
    if (validationErrors.length > 0) {
      logger.warn('Validation failed:', { 
        path: req.path, 
        method: req.method,
        errors: validationErrors 
      });

      return res.status(400).json({
        success: false,
        error: {
          code: 'VALIDATION_ERROR',
          message: 'Invalid request parameters',
          details: validationErrors
        }
      });
    }

    next();
  };
};

/**
 * Common validation schemas
 */
const commonSchemas = {
  zoneId: Joi.string()
    .pattern(/^\d{2}-\d{2}$/)
    .required()
    .description('Zone ID in format pp-zz'),
  
  sectionId: Joi.string()
    .pattern(/^\d{2}-\d{2}-\d{2}-\d{2}$/)
    .required()
    .description('Section ID in format pp-zz-cc-ss'),
  
  weekStart: Joi.date()
    .iso()
    .description('Week start date in ISO format'),
  
  weekEnd: Joi.date()
    .iso()
    .min(Joi.ref('weekStart'))
    .description('Week end date in ISO format'),
  
  executionStatus: Joi.string()
    .valid('pending', 'executing', 'completed', 'failed', 'cancelled')
    .description('Execution status'),
  
  gateType: Joi.string()
    .valid('automatic', 'manual')
    .description('Gate type'),
  
  severity: Joi.string()
    .valid('low', 'medium', 'high', 'critical')
    .description('Severity level')
};

module.exports = {
  validateRequest,
  commonSchemas
};