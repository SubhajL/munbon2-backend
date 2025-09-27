const axios = require('axios');
const NodeCache = require('node-cache');
const { format, startOfWeek, addDays } = require('date-fns');

class WaterDemandIntegrationService {
  constructor(config = {}) {
    this.waterPlanningClient = axios.create({
      baseURL: config.waterPlanningUrl || process.env.WATER_PLANNING_URL || 'http://localhost:3007',
      timeout: config.timeout || 10000,
      headers: {
        'Content-Type': 'application/json'
      }
    });
    
    // Cache for 1 hour to reduce API calls
    this.cache = new NodeCache({ 
      stdTTL: config.cacheTTL || 3600,
      checkperiod: 600 
    });
    
    // Operational parameters
    this.operationalHours = config.operationalHours || 168; // hours per week
    this.deliveryEfficiency = config.deliveryEfficiency || 0.85; // 85% efficiency
    this.criticalStressThreshold = config.criticalStressThreshold || 0.8;
  }
  
  /**
   * Get current week's Monday date
   */
  getCurrentMonday() {
    return format(startOfWeek(new Date(), { weekStartsOn: 1 }), 'yyyy-MM-dd');
  }
  
  /**
   * Get water demands for a specific zone
   */
  async getZoneDemands(zoneId, weekStart = null) {
    const monday = weekStart || this.getCurrentMonday();
    const cacheKey = `zone_demands_${zoneId}_${monday}`;
    
    // Check cache first
    let demands = this.cache.get(cacheKey);
    if (demands) {
      console.log(`Cache hit for zone ${zoneId} demands`);
      return demands;
    }
    
    try {
      // Fetch from Water Planning BFF
      const response = await this.waterPlanningClient.get(
        `/api/v2/water-demand/zones/${zoneId}/weekly`,
        { params: { week_start: monday } }
      );
      
      demands = response.data;
      
      // Validate data freshness
      if (this.isDemandDataStale(demands.calculation_timestamp)) {
        console.warn(`Demand data is stale for zone ${zoneId}, using with caution`);
      }
      
      // Cache the result
      this.cache.set(cacheKey, demands);
      
      return demands;
    } catch (error) {
      console.error(`Failed to fetch demands for zone ${zoneId}:`, error.message);
      
      // Try fallback methods
      return this.getFallbackDemands(zoneId, monday);
    }
  }
  
  /**
   * Get demands for specific sections
   */
  async getSectionDemands(sectionIds, weekStart = null) {
    const monday = weekStart || this.getCurrentMonday();
    const demands = [];
    
    // Batch fetch sections
    const fetchPromises = sectionIds.map(sectionId => 
      this.getSingleSectionDemand(sectionId, monday)
    );
    
    const results = await Promise.allSettled(fetchPromises);
    
    results.forEach((result, index) => {
      if (result.status === 'fulfilled') {
        demands.push(result.value);
      } else {
        console.error(`Failed to fetch demand for section ${sectionIds[index]}`);
      }
    });
    
    return demands;
  }
  
  /**
   * Get demand for a single section
   */
  async getSingleSectionDemand(sectionId, weekStart) {
    const cacheKey = `section_demand_${sectionId}_${weekStart}`;
    
    let demand = this.cache.get(cacheKey);
    if (demand) return demand;
    
    try {
      const response = await this.waterPlanningClient.get(
        `/api/v2/water-demand/sections/${sectionId}/weekly`,
        { params: { week_start: weekStart } }
      );
      
      demand = response.data;
      this.cache.set(cacheKey, demand);
      
      return demand;
    } catch (error) {
      console.error(`Failed to fetch demand for section ${sectionId}:`, error.message);
      throw error;
    }
  }
  
  /**
   * Get stressed areas that need priority irrigation
   */
  async getStressedAreas() {
    const cacheKey = 'stressed_areas';
    
    let stressed = this.cache.get(cacheKey);
    if (stressed) return stressed;
    
    try {
      const response = await this.waterPlanningClient.get('/api/v2/water-demand/stressed-areas');
      stressed = response.data;
      
      // Cache for shorter duration (15 minutes) as this is more dynamic
      this.cache.set(cacheKey, stressed, 900);
      
      return stressed;
    } catch (error) {
      console.error('Failed to fetch stressed areas:', error.message);
      return [];
    }
  }
  
  /**
   * Get current week demands for all sections
   */
  async getCurrentWeekAllSections() {
    const cacheKey = `all_sections_${this.getCurrentMonday()}`;
    
    let demands = this.cache.get(cacheKey);
    if (demands) return demands;
    
    try {
      const response = await this.waterPlanningClient.get('/api/v2/water-demand/current-week/sections');
      demands = response.data;
      this.cache.set(cacheKey, demands);
      
      return demands;
    } catch (error) {
      console.error('Failed to fetch current week demands:', error.message);
      return [];
    }
  }
  
  /**
   * Convert weekly demand to required flow rate
   */
  calculateRequiredFlow(weeklyDemandM3, operationalHours = null) {
    const hours = operationalHours || this.operationalHours;
    const efficiency = this.deliveryEfficiency;
    
    // Convert m³/week to m³/s
    const flowM3s = weeklyDemandM3 / (hours * 3600 * efficiency);
    
    return {
      flow_m3s: flowM3s,
      flow_m3h: flowM3s * 3600,
      flow_lps: flowM3s * 1000,
      efficiency_factor: efficiency,
      operational_hours: hours
    };
  }
  
  /**
   * Calculate priority based on multiple factors
   */
  calculatePriority(demandData, stressedAreas = []) {
    let priority = 5; // Base priority (1-10 scale)
    
    // Check if area is in stressed list
    const isStressed = stressedAreas.some(area => 
      area.area_id === demandData.area_id
    );
    
    if (isStressed) {
      priority += 3;
    }
    
    // Stress indicator factor
    if (demandData.stress_indicator) {
      if (demandData.stress_indicator >= this.criticalStressThreshold) {
        priority += 2;
      } else if (demandData.stress_indicator >= 0.6) {
        priority += 1;
      }
    }
    
    // Delivery efficiency factor
    if (demandData.delivery_efficiency_pct && demandData.delivery_efficiency_pct < 70) {
      priority += 1; // Poor delivery history needs attention
    }
    
    // Sensor adjustment factor
    if (demandData.sensor_adjustment_factor) {
      if (demandData.sensor_adjustment_factor >= 1.15) {
        priority += 1; // High adjustment means water shortage
      }
    }
    
    // Cap at 10
    return Math.min(priority, 10);
  }
  
  /**
   * Generate gate control recommendations based on water demands
   */
  async generateGateRecommendations(zoneId, options = {}) {
    try {
      // 1. Get zone demands
      const zoneDemands = await this.getZoneDemands(zoneId);
      
      // 2. Get stressed areas
      const stressedAreas = await this.getStressedAreas();
      
      // 3. Calculate required flows for each section
      const recommendations = [];
      
      for (const section of zoneDemands.sections || []) {
        const requiredFlow = this.calculateRequiredFlow(section.adjusted_demand_m3);
        const priority = this.calculatePriority(section, stressedAreas);
        
        const recommendation = {
          section_id: section.area_id,
          zone_id: zoneId,
          weekly_demand_m3: section.adjusted_demand_m3,
          required_flow_m3s: requiredFlow.flow_m3s,
          required_flow_lps: requiredFlow.flow_lps,
          priority: priority,
          calculation_method: section.calculation_method,
          sensor_adjustment: section.sensor_adjustment_factor,
          stress_level: section.stress_indicator,
          metadata: {
            calculation_timestamp: zoneDemands.calculation_timestamp,
            operational_hours: requiredFlow.operational_hours,
            delivery_efficiency: requiredFlow.efficiency_factor,
            week_start: zoneDemands.week_start_date
          }
        };
        
        recommendations.push(recommendation);
      }
      
      // 4. Sort by priority
      recommendations.sort((a, b) => b.priority - a.priority);
      
      // 5. Add zone summary
      const summary = {
        zone_id: zoneId,
        total_demand_m3: zoneDemands.total_adjusted_demand_m3,
        total_flow_m3s: recommendations.reduce((sum, r) => sum + r.required_flow_m3s, 0),
        section_count: recommendations.length,
        high_priority_count: recommendations.filter(r => r.priority >= 8).length,
        calculation_timestamp: zoneDemands.calculation_timestamp
      };
      
      return {
        recommendations,
        summary,
        stressed_areas: stressedAreas.filter(a => a.zone_id === zoneId)
      };
    } catch (error) {
      console.error('Failed to generate gate recommendations:', error);
      throw error;
    }
  }
  
  /**
   * Check if demand data is stale
   */
  isDemandDataStale(timestamp) {
    if (!timestamp) return true;
    
    const dataAge = Date.now() - new Date(timestamp).getTime();
    const maxAge = 7 * 24 * 60 * 60 * 1000; // 7 days
    
    return dataAge > maxAge;
  }
  
  /**
   * Get fallback demands when API fails
   */
  async getFallbackDemands(zoneId, weekStart) {
    // Try to get from cache with any date
    const keys = this.cache.keys();
    const zoneKeys = keys.filter(k => k.includes(`zone_demands_${zoneId}`));
    
    if (zoneKeys.length > 0) {
      console.log(`Using cached demands from previous week for zone ${zoneId}`);
      return this.cache.get(zoneKeys[0]);
    }
    
    // Return basic structure with estimated values
    console.warn(`Using estimated demands for zone ${zoneId}`);
    return {
      zone_id: zoneId,
      week_start_date: weekStart,
      total_adjusted_demand_m3: 50000, // Default 50,000 m³/week
      sections: [],
      calculation_method: 'fallback',
      calculation_timestamp: new Date().toISOString()
    };
  }
  
  /**
   * Clear cache
   */
  clearCache() {
    this.cache.flushAll();
    console.log('Water demand cache cleared');
  }
  
  /**
   * Get cache statistics
   */
  getCacheStats() {
    return {
      keys: this.cache.keys().length,
      stats: this.cache.getStats()
    };
  }
}

module.exports = WaterDemandIntegrationService;