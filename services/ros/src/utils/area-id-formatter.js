/**
 * Area ID Formatter and Validator
 * Handles PP-ZZ-CC-SS format where:
 * PP = Project code (2 digits)
 * ZZ = Zone code (2 digits)
 * CC = Canal code (2 digits)
 * SS = Section code (2 digits)
 */

class AreaIdFormatter {
  /**
   * Validate if area ID matches PP-ZZ-CC-SS format
   * @param {string} areaId - Area ID to validate
   * @returns {boolean} - True if valid format
   */
  static isValidFormat(areaId) {
    const pattern = /^[0-9]{2}-[0-9]{2}-[0-9]{2}-[0-9]{2}$/;
    return pattern.test(areaId);
  }

  /**
   * Parse area ID into components
   * @param {string} areaId - Area ID in PP-ZZ-CC-SS format
   * @returns {Object|null} - Components object or null if invalid
   */
  static parseAreaId(areaId) {
    if (!this.isValidFormat(areaId)) {
      return null;
    }

    const parts = areaId.split('-');
    return {
      projectCode: parts[0],
      zoneCode: parts[1],
      canalCode: parts[2],
      sectionCode: parts[3],
      fullId: areaId
    };
  }

  /**
   * Create area ID from components
   * @param {string} projectCode - Project code (2 digits)
   * @param {string} zoneCode - Zone code (2 digits)
   * @param {string} canalCode - Canal code (2 digits)
   * @param {string} sectionCode - Section code (2 digits)
   * @returns {string|null} - Formatted area ID or null if invalid
   */
  static createAreaId(projectCode, zoneCode, canalCode, sectionCode) {
    // Validate each component
    const components = [projectCode, zoneCode, canalCode, sectionCode];
    
    for (const component of components) {
      if (!component || !/^[0-9]{2}$/.test(component)) {
        return null;
      }
    }

    return `${projectCode}-${zoneCode}-${canalCode}-${sectionCode}`;
  }

  /**
   * Get area type based on components
   * @param {string} areaId - Area ID in PP-ZZ-CC-SS format
   * @returns {string|null} - Area type or null if invalid
   */
  static getAreaType(areaId) {
    const components = this.parseAreaId(areaId);
    if (!components) return null;

    if (components.zoneCode === '00' && components.canalCode === '00' && components.sectionCode === '00') {
      return 'project';
    } else if (components.canalCode === '00' && components.sectionCode === '00') {
      return 'zone';
    } else if (components.sectionCode === '00') {
      return 'canal';
    } else {
      return 'section';
    }
  }

  /**
   * Get parent area ID
   * @param {string} areaId - Area ID in PP-ZZ-CC-SS format
   * @returns {string|null} - Parent area ID or null if no parent
   */
  static getParentAreaId(areaId) {
    const components = this.parseAreaId(areaId);
    if (!components) return null;

    const areaType = this.getAreaType(areaId);
    
    switch (areaType) {
      case 'project':
        return null; // No parent for project
      case 'zone':
        return this.createAreaId(components.projectCode, '00', '00', '00');
      case 'canal':
        return this.createAreaId(components.projectCode, components.zoneCode, '00', '00');
      case 'section':
        return this.createAreaId(components.projectCode, components.zoneCode, components.canalCode, '00');
      default:
        return null;
    }
  }

  /**
   * Get all ancestor area IDs (from section up to project)
   * @param {string} areaId - Area ID in PP-ZZ-CC-SS format
   * @returns {Array<string>} - Array of ancestor area IDs
   */
  static getAncestorAreaIds(areaId) {
    const ancestors = [];
    const components = this.parseAreaId(areaId);
    if (!components) return ancestors;

    // Add project level
    const projectId = this.createAreaId(components.projectCode, '00', '00', '00');
    ancestors.push(projectId);

    // Add zone level if applicable
    if (components.zoneCode !== '00') {
      const zoneId = this.createAreaId(components.projectCode, components.zoneCode, '00', '00');
      ancestors.push(zoneId);
    }

    // Add canal level if applicable
    if (components.canalCode !== '00') {
      const canalId = this.createAreaId(components.projectCode, components.zoneCode, components.canalCode, '00');
      ancestors.push(canalId);
    }

    // Add current level if it's a section
    if (components.sectionCode !== '00') {
      ancestors.push(areaId);
    }

    return ancestors;
  }

  /**
   * Convert old format to new format (migration helper)
   * @param {string} oldAreaId - Old area ID format
   * @param {string} areaType - Area type
   * @param {string} projectCode - Project code (default '01')
   * @returns {string|null} - New format area ID or null if cannot convert
   */
  static convertFromOldFormat(oldAreaId, areaType, projectCode = '01') {
    try {
      switch (areaType) {
        case 'project':
          return this.createAreaId(projectCode, '00', '00', '00');
        
        case 'zone':
          // Extract zone number from formats like 'Z1', 'Zone1', etc.
          const zoneMatch = oldAreaId.match(/[Zz]one?\s*(\d+)/);
          if (zoneMatch) {
            const zoneCode = zoneMatch[1].padStart(2, '0');
            return this.createAreaId(projectCode, zoneCode, '00', '00');
          }
          break;
        
        case 'section':
          // Extract from formats like 'Z1-001', 'Zone1-Section001', etc.
          const sectionMatch = oldAreaId.match(/[Zz]one?\s*(\d+)[-\s]+[Ss]ection?\s*(\d+)/);
          if (sectionMatch) {
            const zoneCode = sectionMatch[1].padStart(2, '0');
            const sectionCode = sectionMatch[2].padStart(2, '0');
            // Default canal code to '01' for now
            return this.createAreaId(projectCode, zoneCode, '01', sectionCode);
          }
          break;
      }
    } catch (error) {
      console.error('Error converting area ID:', error);
    }
    
    return null;
  }

  /**
   * Format area ID for display
   * @param {string} areaId - Area ID in PP-ZZ-CC-SS format
   * @param {boolean} includeLabels - Whether to include labels
   * @returns {string} - Formatted display string
   */
  static formatForDisplay(areaId, includeLabels = false) {
    const components = this.parseAreaId(areaId);
    if (!components) return areaId;

    if (includeLabels) {
      const areaType = this.getAreaType(areaId);
      const parts = [];
      
      parts.push(`Project ${components.projectCode}`);
      
      if (components.zoneCode !== '00') {
        parts.push(`Zone ${components.zoneCode}`);
      }
      
      if (components.canalCode !== '00') {
        parts.push(`Canal ${components.canalCode}`);
      }
      
      if (components.sectionCode !== '00') {
        parts.push(`Section ${components.sectionCode}`);
      }
      
      return parts.join(' > ');
    }
    
    return areaId;
  }
}

module.exports = AreaIdFormatter;