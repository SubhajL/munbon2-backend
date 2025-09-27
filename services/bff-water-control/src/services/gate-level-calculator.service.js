const gateConfigs = require('../config/gate-levels.json');

class GateLevelCalculatorService {
  constructor() {
    this.gateConfigs = gateConfigs.automatic_gates;
    
    // Flow coefficients for different gate types (m³/s per cm opening)
    // These should be calibrated based on actual field measurements
    this.flowCoefficients = {
      'RMC': 0.025,  // Right Main Canal gates
      'LMC': 0.025,  // Left Main Canal gates
      'RBC': 0.020,  // Right Branch Canal gates
      'LBC': 0.020,  // Left Branch Canal gates
      'default': 0.022
    };
    
    // Gate capacity limits (m³/s)
    this.gateCapacities = {
      'RMC1': 3.5, 'RMC2': 3.5, 'RMC3': 3.5, 'RMC4': 3.5,
      'LMC1': 3.5, 'LMC2': 3.5, 'LMC3': 3.5, 'LMC4': 3.5,
      'RBC1': 2.5, 'RBC2': 2.5, 'RBC3': 2.5, 'RBC4': 2.5,
      'LBC1': 2.5, 'LBC2': 2.5, 'LBC3': 2.5,
      'LBCM1': 2.0, 'LBCM2': 2.0, 'LBCM3': 2.0
    };
  }
  
  /**
   * Calculate gate level (1-4) from required flow
   */
  calculateGateLevelFromFlow(gateName, requiredFlowM3s) {
    const gateConfig = this.gateConfigs[gateName];
    if (!gateConfig) {
      throw new Error(`Gate configuration not found for ${gateName}`);
    }
    
    // Get flow coefficient for this gate type
    const gateType = gateName.substring(0, 3);
    const flowCoeff = this.flowCoefficients[gateType] || this.flowCoefficients.default;
    
    // Calculate required opening in cm
    const requiredOpeningCm = requiredFlowM3s / flowCoeff;
    
    // Check capacity limit
    const capacity = this.gateCapacities[gateName] || 3.0;
    if (requiredFlowM3s > capacity) {
      console.warn(`Required flow ${requiredFlowM3s} m³/s exceeds gate ${gateName} capacity ${capacity} m³/s`);
    }
    
    // Determine appropriate level based on cumulative openings
    const levels = gateConfig.cumulative_levels;
    let selectedLevel = 1;
    let selectedOpening = levels.level_1;
    
    if (requiredOpeningCm <= levels.level_1) {
      selectedLevel = 1;
      selectedOpening = levels.level_1;
    } else if (requiredOpeningCm <= levels.level_2) {
      selectedLevel = 2;
      selectedOpening = levels.level_2;
    } else if (requiredOpeningCm <= levels.level_3) {
      selectedLevel = 3;
      selectedOpening = levels.level_3;
    } else {
      selectedLevel = 4;
      selectedOpening = levels.level_4;
    }
    
    // Calculate actual flow at selected level
    const actualFlowM3s = selectedOpening * flowCoeff;
    
    return {
      gate_name: gateName,
      required_flow_m3s: requiredFlowM3s,
      required_opening_cm: requiredOpeningCm,
      selected_level: selectedLevel,
      selected_opening_cm: selectedOpening,
      actual_flow_m3s: actualFlowM3s,
      flow_difference_pct: ((actualFlowM3s - requiredFlowM3s) / requiredFlowM3s * 100).toFixed(1),
      capacity_utilization_pct: (requiredFlowM3s / capacity * 100).toFixed(1)
    };
  }
  
  /**
   * Calculate gate settings for multiple delivery points
   */
  calculateMultipleGateSettings(flowRequirements) {
    const gateSettings = [];
    const gateFlows = new Map(); // Track cumulative flows per gate
    
    // Group flow requirements by gate
    flowRequirements.forEach(req => {
      const currentFlow = gateFlows.get(req.gate_name) || 0;
      gateFlows.set(req.gate_name, currentFlow + req.flow_m3s);
    });
    
    // Calculate settings for each gate
    for (const [gateName, totalFlow] of gateFlows) {
      try {
        const setting = this.calculateGateLevelFromFlow(gateName, totalFlow);
        gateSettings.push(setting);
      } catch (error) {
        console.error(`Failed to calculate setting for gate ${gateName}:`, error.message);
      }
    }
    
    return gateSettings;
  }
  
  /**
   * Convert section demands to gate requirements
   */
  convertDemandsToGateRequirements(demands, gateMapping) {
    const gateRequirements = [];
    
    demands.recommendations.forEach(demand => {
      // Find gates serving this section
      const gates = this.findGatesForSection(demand.section_id, gateMapping);
      
      if (gates.length === 0) {
        console.warn(`No gates found for section ${demand.section_id}`);
        return;
      }
      
      // Distribute flow among serving gates
      const flowPerGate = demand.required_flow_m3s / gates.length;
      
      gates.forEach(gate => {
        gateRequirements.push({
          gate_name: gate.gate_name,
          section_id: demand.section_id,
          flow_m3s: flowPerGate,
          priority: demand.priority,
          demand_metadata: {
            weekly_demand_m3: demand.weekly_demand_m3,
            stress_level: demand.stress_level,
            sensor_adjustment: demand.sensor_adjustment
          }
        });
      });
    });
    
    return gateRequirements;
  }
  
  /**
   * Find gates that serve a specific section
   */
  findGatesForSection(sectionId, gateMapping) {
    // Extract zone from section ID (pp-zz-cc-ss format)
    const [project, zone, canal, section] = sectionId.split('-');
    
    // Default mapping based on zone and canal
    // This should be replaced with actual network topology
    const gates = [];
    
    // Main canal gates based on zone
    if (zone === '01' || zone === '02') {
      gates.push({ gate_name: 'RMC1', position: 'upstream' });
      gates.push({ gate_name: 'RMC2', position: 'midstream' });
    } else if (zone === '03' || zone === '04') {
      gates.push({ gate_name: 'LMC1', position: 'upstream' });
      gates.push({ gate_name: 'LMC2', position: 'midstream' });
    }
    
    // Branch canal gates based on canal number
    if (canal === '01' || canal === '02') {
      gates.push({ gate_name: `RBC${canal}`, position: 'branch' });
    } else if (canal === '03' || canal === '04') {
      gates.push({ gate_name: `LBC${canal}`, position: 'branch' });
    }
    
    // Override with custom mapping if provided
    if (gateMapping && gateMapping[sectionId]) {
      return gateMapping[sectionId];
    }
    
    return gates;
  }
  
  /**
   * Optimize gate settings to minimize operations
   */
  optimizeGateSettings(gateSettings, currentGateStates = {}) {
    const optimized = [...gateSettings];
    
    // Sort by priority and flow magnitude
    optimized.sort((a, b) => {
      // First by flow magnitude (larger flows first)
      const flowDiff = b.required_flow_m3s - a.required_flow_m3s;
      if (Math.abs(flowDiff) > 0.1) return flowDiff;
      
      // Then by current state difference (minimize changes)
      const currentA = currentGateStates[a.gate_name]?.level || 0;
      const currentB = currentGateStates[b.gate_name]?.level || 0;
      const changeA = Math.abs(a.selected_level - currentA);
      const changeB = Math.abs(b.selected_level - currentB);
      
      return changeA - changeB;
    });
    
    // Group sequential operations
    const operations = [];
    let currentGroup = [];
    
    optimized.forEach((setting, index) => {
      if (currentGroup.length === 0) {
        currentGroup.push(setting);
      } else {
        const lastGate = currentGroup[currentGroup.length - 1];
        
        // Group if same canal type and adjacent
        if (this.areGatesAdjacent(lastGate.gate_name, setting.gate_name)) {
          currentGroup.push(setting);
        } else {
          operations.push({
            gates: [...currentGroup],
            type: 'sequential',
            total_flow: currentGroup.reduce((sum, g) => sum + g.actual_flow_m3s, 0)
          });
          currentGroup = [setting];
        }
      }
    });
    
    // Add last group
    if (currentGroup.length > 0) {
      operations.push({
        gates: currentGroup,
        type: 'sequential',
        total_flow: currentGroup.reduce((sum, g) => sum + g.actual_flow_m3s, 0)
      });
    }
    
    return {
      individual_settings: optimized,
      operation_groups: operations,
      total_gates: optimized.length,
      total_flow: optimized.reduce((sum, g) => sum + g.actual_flow_m3s, 0)
    };
  }
  
  /**
   * Check if two gates are adjacent in the network
   */
  areGatesAdjacent(gate1, gate2) {
    // Extract gate type and number
    const type1 = gate1.substring(0, 3);
    const num1 = parseInt(gate1.substring(3));
    const type2 = gate2.substring(0, 3);
    const num2 = parseInt(gate2.substring(3));
    
    // Same type and consecutive numbers
    return type1 === type2 && Math.abs(num1 - num2) === 1;
  }
  
  /**
   * Generate gate control sequence with timing
   */
  generateControlSequence(optimizedSettings, options = {}) {
    const sequence = [];
    const baseDelay = options.baseDelay || 5; // minutes between operations
    const groupDelay = options.groupDelay || 15; // minutes between groups
    
    let currentTime = new Date();
    
    optimizedSettings.operation_groups.forEach((group, groupIndex) => {
      group.gates.forEach((gate, gateIndex) => {
        const operation = {
          sequence: sequence.length + 1,
          gate_name: gate.gate_name,
          target_level: gate.selected_level,
          target_opening_cm: gate.selected_opening_cm,
          expected_flow_m3s: gate.actual_flow_m3s,
          scheduled_time: new Date(currentTime),
          group_id: groupIndex + 1,
          priority: gate.priority || 5,
          metadata: {
            required_flow: gate.required_flow_m3s,
            capacity_utilization: gate.capacity_utilization_pct,
            flow_accuracy: gate.flow_difference_pct
          }
        };
        
        sequence.push(operation);
        
        // Add delay for next operation
        currentTime = new Date(currentTime.getTime() + baseDelay * 60 * 1000);
      });
      
      // Add group delay
      currentTime = new Date(currentTime.getTime() + groupDelay * 60 * 1000);
    });
    
    return {
      sequence,
      total_duration_minutes: (sequence[sequence.length - 1].scheduled_time - sequence[0].scheduled_time) / 60000,
      operation_count: sequence.length,
      group_count: optimizedSettings.operation_groups.length
    };
  }
  
  /**
   * Validate gate settings against constraints
   */
  validateGateSettings(gateSettings, constraints = {}) {
    const validations = {
      valid: true,
      warnings: [],
      errors: []
    };
    
    gateSettings.forEach(setting => {
      // Check capacity limits
      if (parseFloat(setting.capacity_utilization_pct) > 90) {
        validations.warnings.push({
          gate: setting.gate_name,
          issue: 'High capacity utilization',
          value: `${setting.capacity_utilization_pct}%`
        });
      }
      
      // Check flow accuracy
      const flowDiff = Math.abs(parseFloat(setting.flow_difference_pct));
      if (flowDiff > 20) {
        validations.warnings.push({
          gate: setting.gate_name,
          issue: 'Large flow difference',
          value: `${setting.flow_difference_pct}%`
        });
      }
      
      // Check maximum opening
      if (setting.selected_level === 4 && parseFloat(setting.capacity_utilization_pct) > 95) {
        validations.errors.push({
          gate: setting.gate_name,
          issue: 'Insufficient capacity',
          required: `${setting.required_flow_m3s} m³/s`,
          available: `${setting.actual_flow_m3s} m³/s`
        });
        validations.valid = false;
      }
    });
    
    // Check total flow constraints
    if (constraints.maxTotalFlow) {
      const totalFlow = gateSettings.reduce((sum, g) => sum + g.actual_flow_m3s, 0);
      if (totalFlow > constraints.maxTotalFlow) {
        validations.errors.push({
          issue: 'Total flow exceeds limit',
          total: `${totalFlow.toFixed(2)} m³/s`,
          limit: `${constraints.maxTotalFlow} m³/s`
        });
        validations.valid = false;
      }
    }
    
    return validations;
  }
}

module.exports = GateLevelCalculatorService;