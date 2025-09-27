const AreaIdFormatter = require('../utils/area-id-formatter');

/**
 * Middleware to validate area ID format in requests
 */
const validateAreaId = (paramName = 'areaId') => {
  return (req, res, next) => {
    const areaId = req.params[paramName] || req.query[paramName] || req.body[paramName];
    
    if (!areaId) {
      return res.status(400).json({
        success: false,
        error: 'Area ID is required',
        code: 'AREA_ID_REQUIRED'
      });
    }

    if (!AreaIdFormatter.isValidFormat(areaId)) {
      return res.status(400).json({
        success: false,
        error: 'Invalid area ID format. Expected format: PP-ZZ-CC-SS (e.g., 01-02-03-04)',
        code: 'INVALID_AREA_ID_FORMAT',
        receivedValue: areaId
      });
    }

    // Parse and attach components to request for easy access
    const components = AreaIdFormatter.parseAreaId(areaId);
    req.areaComponents = components;
    req.areaType = AreaIdFormatter.getAreaType(areaId);
    
    next();
  };
};

/**
 * Middleware to validate multiple area IDs in request
 */
const validateAreaIds = (paramName = 'areaIds') => {
  return (req, res, next) => {
    const areaIds = req.body[paramName] || req.query[paramName];
    
    if (!areaIds || !Array.isArray(areaIds) || areaIds.length === 0) {
      return res.status(400).json({
        success: false,
        error: 'Area IDs array is required',
        code: 'AREA_IDS_REQUIRED'
      });
    }

    const invalidIds = [];
    const validComponents = [];

    areaIds.forEach(areaId => {
      if (!AreaIdFormatter.isValidFormat(areaId)) {
        invalidIds.push(areaId);
      } else {
        validComponents.push({
          areaId,
          components: AreaIdFormatter.parseAreaId(areaId),
          areaType: AreaIdFormatter.getAreaType(areaId)
        });
      }
    });

    if (invalidIds.length > 0) {
      return res.status(400).json({
        success: false,
        error: 'Invalid area ID format found',
        code: 'INVALID_AREA_ID_FORMAT',
        invalidIds,
        expectedFormat: 'PP-ZZ-CC-SS (e.g., 01-02-03-04)'
      });
    }

    req.areaComponents = validComponents;
    next();
  };
};

/**
 * Middleware to validate area hierarchy in request
 * Ensures parent-child relationships are valid
 */
const validateAreaHierarchy = () => {
  return (req, res, next) => {
    const { areaId, parentAreaId } = req.body;
    
    if (!areaId || !parentAreaId) {
      return next(); // Skip validation if not both present
    }

    if (!AreaIdFormatter.isValidFormat(areaId) || !AreaIdFormatter.isValidFormat(parentAreaId)) {
      return res.status(400).json({
        success: false,
        error: 'Invalid area ID format',
        code: 'INVALID_AREA_ID_FORMAT'
      });
    }

    const childComponents = AreaIdFormatter.parseAreaId(areaId);
    const parentComponents = AreaIdFormatter.parseAreaId(parentAreaId);
    const expectedParentId = AreaIdFormatter.getParentAreaId(areaId);

    // Check if the parent-child relationship is valid
    if (expectedParentId !== parentAreaId) {
      return res.status(400).json({
        success: false,
        error: 'Invalid area hierarchy',
        code: 'INVALID_AREA_HIERARCHY',
        message: `Area ${areaId} cannot have parent ${parentAreaId}`,
        expectedParent: expectedParentId
      });
    }

    next();
  };
};

/**
 * Middleware to transform old area ID format to new format
 * Useful during migration period
 */
const transformLegacyAreaId = (paramName = 'areaId') => {
  return (req, res, next) => {
    const areaId = req.params[paramName] || req.query[paramName] || req.body[paramName];
    const areaType = req.body.areaType || req.query.areaType;
    
    if (!areaId) {
      return next();
    }

    // Check if already in new format
    if (AreaIdFormatter.isValidFormat(areaId)) {
      return next();
    }

    // Try to convert from old format
    if (areaType) {
      const newAreaId = AreaIdFormatter.convertFromOldFormat(areaId, areaType);
      
      if (newAreaId) {
        // Replace the old ID with new format
        if (req.params[paramName]) req.params[paramName] = newAreaId;
        if (req.query[paramName]) req.query[paramName] = newAreaId;
        if (req.body[paramName]) req.body[paramName] = newAreaId;
        
        req.areaIdTransformed = true;
        req.originalAreaId = areaId;
        
        return next();
      }
    }

    // If we can't transform, let the validation middleware handle it
    next();
  };
};

module.exports = {
  validateAreaId,
  validateAreaIds,
  validateAreaHierarchy,
  transformLegacyAreaId
};