const { query, body, param, validationResult } = require('express-validator');

// Validation schemas
const validationSchemas = {
  // Common validators
  zone: query('zone')
    .optional()
    .matches(/^Z[0-9]+$/)
    .withMessage('Zone must be in format Z1, Z2, etc.'),
  
  date: query('date')
    .optional()
    .matches(/^[0-9]{2}\/[0-9]{2}\/[0-9]{4}$/)
    .withMessage('Date must be in Buddhist calendar format DD/MM/YYYY'),
  
  startDate: query('start')
    .matches(/^[0-9]{2}\/[0-9]{2}\/[0-9]{4}$/)
    .withMessage('Start date must be in Buddhist calendar format DD/MM/YYYY'),
  
  endDate: query('end')
    .matches(/^[0-9]{2}\/[0-9]{2}\/[0-9]{4}$/)
    .withMessage('End date must be in Buddhist calendar format DD/MM/YYYY'),
  
  page: query('page')
    .optional()
    .isInt({ min: 1 })
    .withMessage('Page must be a positive integer'),
  
  limit: query('limit')
    .optional()
    .isInt({ min: 1, max: 100 })
    .withMessage('Limit must be between 1 and 100'),
  
  severity: query('severity')
    .optional()
    .isIn(['critical', 'warning', 'info'])
    .withMessage('Severity must be critical, warning, or info'),
  
  active: query('active')
    .optional()
    .isBoolean()
    .withMessage('Active must be a boolean value'),

  // ETO calculation validators
  etoTemperature: body('temperature')
    .isFloat({ min: -50, max: 60 })
    .withMessage('Temperature must be between -50 and 60°C'),
  
  etoHumidity: body('humidity')
    .isFloat({ min: 0, max: 100 })
    .withMessage('Humidity must be between 0 and 100%'),
  
  etoWindSpeed: body('windSpeed')
    .isFloat({ min: 0, max: 50 })
    .withMessage('Wind speed must be between 0 and 50 m/s'),
  
  etoSolarRadiation: body('solarRadiation')
    .isFloat({ min: 0, max: 50 })
    .withMessage('Solar radiation must be between 0 and 50 MJ/m²/day'),
  
  etoLatitude: body('latitude')
    .isFloat({ min: -90, max: 90 })
    .withMessage('Latitude must be between -90 and 90 degrees')
};

// Validation rules for each endpoint
const validationRules = {
  // Dashboard endpoints
  dashboardSummary: [
    validationSchemas.zone,
    validationSchemas.date
  ],
  
  alerts: [
    validationSchemas.zone,
    validationSchemas.severity,
    validationSchemas.active
  ],
  
  // Sensor endpoints
  waterLevelLatest: [
    validationSchemas.zone
  ],
  
  waterLevelTimeseries: [
    validationSchemas.startDate,
    validationSchemas.endDate,
    validationSchemas.zone
  ],
  
  waterLevelStatistics: [
    validationSchemas.date.notEmpty().withMessage('Date is required'),
    validationSchemas.zone
  ],
  
  moistureLatest: [
    validationSchemas.zone
  ],
  
  moistureTimeseries: [
    validationSchemas.date.notEmpty().withMessage('Date is required'),
    validationSchemas.zone
  ],
  
  // Analytics endpoints
  waterDemand: [
    validationSchemas.zone,
    validationSchemas.date
  ],
  
  irrigationSchedule: [
    validationSchemas.zone
  ],
  
  calculateETO: [
    validationSchemas.etoTemperature,
    validationSchemas.etoHumidity,
    validationSchemas.etoWindSpeed,
    validationSchemas.etoSolarRadiation,
    validationSchemas.etoLatitude
  ],
  
  // GIS endpoints
  parcels: [
    validationSchemas.zone,
    validationSchemas.page,
    validationSchemas.limit
  ],
  
  parcelById: [
    param('parcelId')
      .notEmpty()
      .withMessage('Parcel ID is required')
      .matches(/^P[0-9]+$/)
      .withMessage('Invalid parcel ID format')
  ],
  
  zones: [
    // No specific validation needed
  ],
  
  zoneById: [
    param('zoneId')
      .notEmpty()
      .withMessage('Zone ID is required')
      .matches(/^Z[0-9]+$/)
      .withMessage('Invalid zone ID format')
  ]
};

// Validation error handler
const handleValidationErrors = (req, res, next) => {
  const errors = validationResult(req);
  
  if (!errors.isEmpty()) {
    return res.status(400).json({
      success: false,
      error: {
        code: 'VALIDATION_ERROR',
        message: 'Invalid request parameters',
        details: errors.array().reduce((acc, error) => {
          acc[error.param] = error.msg;
          return acc;
        }, {}),
        timestamp: new Date().toISOString()
      },
      meta: {
        requestId: req.id,
        documentation: 'https://api.munbon.go.th/docs#validation'
      }
    });
  }
  
  next();
};

// Custom validators
const customValidators = {
  // Validate date range
  validateDateRange: (req, res, next) => {
    if (req.query.start && req.query.end) {
      const startDate = parseBuddhistDate(req.query.start);
      const endDate = parseBuddhistDate(req.query.end);
      
      if (startDate > endDate) {
        return res.status(400).json({
          success: false,
          error: {
            code: 'INVALID_DATE_RANGE',
            message: 'Start date must be before end date',
            timestamp: new Date().toISOString()
          },
          meta: {
            requestId: req.id
          }
        });
      }
      
      // Maximum date range: 30 days
      const daysDiff = (endDate - startDate) / (1000 * 60 * 60 * 24);
      if (daysDiff > 30) {
        return res.status(400).json({
          success: false,
          error: {
            code: 'DATE_RANGE_TOO_LARGE',
            message: 'Date range cannot exceed 30 days',
            timestamp: new Date().toISOString()
          },
          meta: {
            requestId: req.id
          }
        });
      }
    }
    
    next();
  },
  
  // Validate coordinates
  validateCoordinates: (req, res, next) => {
    if (req.body.location) {
      const { lat, lng } = req.body.location;
      
      // Thailand approximate bounds
      if (lat < 5.5 || lat > 20.5 || lng < 97.3 || lng > 105.7) {
        return res.status(400).json({
          success: false,
          error: {
            code: 'INVALID_COORDINATES',
            message: 'Coordinates are outside Thailand boundaries',
            timestamp: new Date().toISOString()
          },
          meta: {
            requestId: req.id
          }
        });
      }
    }
    
    next();
  }
};

// Helper function to parse Buddhist date
const parseBuddhistDate = (dateStr) => {
  const [day, month, year] = dateStr.split('/').map(Number);
  return new Date(year - 543, month - 1, day);
};

// Export validation middleware factory
const validate = (validationName) => {
  const rules = validationRules[validationName];
  if (!rules) {
    throw new Error(`No validation rules found for: ${validationName}`);
  }
  
  return [
    ...rules,
    handleValidationErrors,
    ...(validationName.includes('Timeseries') ? [customValidators.validateDateRange] : [])
  ];
};

module.exports = {
  validate,
  validationRules,
  customValidators,
  handleValidationErrors
};