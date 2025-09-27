const { comprehensiveGateMapping } = require('../config/comprehensive-gate-mapping');

class HydraulicCalculatorService {
  constructor() {
    // Hydraulic coefficients for gate flow calculations
    this.flowCoefficients = {
      automatic: {
        level_1: { opening_cm: 20, flow_factor: 0.5 },
        level_2: { opening_cm: 40, flow_factor: 1.0 },
        level_3: { opening_cm: 60, flow_factor: 1.5 },
        level_4: { opening_cm: 80, flow_factor: 2.0 }
      },
      manual: {
        // Manual gates have variable opening based on flow needs
        min_opening_cm: 10,
        max_opening_cm: 40,
        flow_per_cm: 0.025 // m³/s per cm of opening
      }
    };

    // Operational parameters
    this.operationalParams = {
      weekly_hours: 168,
      efficiency_factor: 0.85, // 85% operational efficiency
      daily_operation_hours: {
        high_priority: 16,    // 5am - 9pm for high priority areas
        medium_priority: 12,  // 6am - 6pm for medium priority
        low_priority: 10      // 7am - 5pm for low priority
      },
      gate_operation_schedule: {
        automatic: {
          start_times: ['05:00', '06:00', '07:00'],
          end_times: ['18:00', '19:00', '20:00', '21:00']
        },
        manual: {
          morning_shift: { start: '06:00', end: '12:00' },
          afternoon_shift: { start: '13:00', end: '18:00' },
          full_day: { start: '06:00', end: '18:00' }
        }
      }
    };
  }

  /**
   * Calculate gate settings for a section based on water demand
   */
  calculateGateSettingsForSection(sectionDemand, gates, weekNumber) {
    const demandM3 = parseFloat(sectionDemand.adjusted_demand_m3);
    const priority = this.calculatePriority(sectionDemand, weekNumber);
    
    // Calculate required flow rate
    const operationalHours = this.getOperationalHours(priority);
    const requiredFlowM3s = demandM3 / (operationalHours * 3600);
    
    // Separate automatic and manual gates
    const automaticGates = gates.filter(g => g.type === 'automatic');
    const manualGates = gates.filter(g => g.type === 'manual');
    
    // Distribute flow: 70% automatic, 30% manual (if both exist)
    const autoFlowRatio = automaticGates.length > 0 ? 0.7 : 0;
    const manualFlowRatio = manualGates.length > 0 ? (automaticGates.length > 0 ? 0.3 : 1.0) : 0;
    
    const gateSettings = [];
    
    // Calculate automatic gate settings
    if (automaticGates.length > 0) {
      const autoSettings = this.calculateAutomaticGateSettings(
        automaticGates, 
        requiredFlowM3s * autoFlowRatio, 
        priority, 
        weekNumber
      );
      gateSettings.push(...autoSettings);
    }
    
    // Calculate manual gate settings
    if (manualGates.length > 0) {
      const manualSettings = this.calculateManualGateSettings(
        manualGates, 
        requiredFlowM3s * manualFlowRatio, 
        priority, 
        weekNumber,
        sectionDemand
      );
      gateSettings.push(...manualSettings);
    }
    
    return gateSettings;
  }

  /**
   * Calculate automatic gate settings
   */
  calculateAutomaticGateSettings(gates, totalFlowM3s, priority, weekNumber) {
    const settings = [];
    const flowPerGate = totalFlowM3s / gates.length;
    
    // Get operation schedule based on priority
    const schedule = this.getAutomaticGateSchedule(priority, weekNumber);
    
    for (const gate of gates) {
      // Calculate required gate level based on flow
      const gateCapacity = gate.capacity_cms || 2.5; // Default 2.5 m³/s capacity
      const flowRatio = flowPerGate / gateCapacity;
      
      let gateLevel, cumulativeOpening;
      
      if (flowRatio <= 0.25) {
        gateLevel = 1;
        cumulativeOpening = 20;
      } else if (flowRatio <= 0.5) {
        gateLevel = 2;
        cumulativeOpening = 40;
      } else if (flowRatio <= 0.75) {
        gateLevel = 3;
        cumulativeOpening = 60;
      } else {
        gateLevel = 4;
        cumulativeOpening = 80;
      }
      
      // Adjust based on week progression (gradually increase for growing crops)
      if (weekNumber >= 3 && weekNumber <= 5) {
        gateLevel = Math.min(4, gateLevel + 1);
        cumulativeOpening = Math.min(80, cumulativeOpening + 20);
      }
      
      // Calculate actual flow for this gate level
      const actualFlowM3s = gateCapacity * (cumulativeOpening / 80);
      const operationHours = this.calculateHoursDiff(schedule.open_time, schedule.close_time);
      const expectedVolumeM3 = actualFlowM3s * operationHours * 3600;
      
      settings.push({
        gate_id: gate.name,
        gate_type: 'automatic',
        gate_location: gate.location,
        gate_level: gateLevel,
        cumulative_opening_cm: cumulativeOpening,
        open_time: schedule.open_time,
        close_time: schedule.close_time,
        operation_duration_hours: operationHours,
        target_flow_m3s: actualFlowM3s,
        expected_volume_m3: expectedVolumeM3
      });
    }
    
    return settings;
  }

  /**
   * Calculate manual gate settings
   */
  calculateManualGateSettings(gates, totalFlowM3s, priority, weekNumber, sectionDemand) {
    const settings = [];
    const flowPerGate = totalFlowM3s / gates.length;
    
    for (let i = 0; i < gates.length; i++) {
      const gate = gates[i];
      
      // Calculate opening height based on required flow
      const requiredOpeningCm = Math.round(flowPerGate / this.flowCoefficients.manual.flow_per_cm);
      const openingHeight = Math.max(
        this.flowCoefficients.manual.min_opening_cm,
        Math.min(this.flowCoefficients.manual.max_opening_cm, requiredOpeningCm)
      );
      
      // Vary schedule based on gate index and priority
      const schedule = this.getManualGateSchedule(i, priority, weekNumber);
      
      // Adjust opening height based on water level status
      let adjustedHeight = openingHeight;
      if (sectionDemand.water_level_status === 'low') {
        adjustedHeight = Math.min(this.flowCoefficients.manual.max_opening_cm, openingHeight * 1.2);
      } else if (sectionDemand.water_level_status === 'high') {
        adjustedHeight = Math.max(this.flowCoefficients.manual.min_opening_cm, openingHeight * 0.8);
      }
      
      // Round to nearest 5cm for practical operation
      adjustedHeight = Math.round(adjustedHeight / 5) * 5;
      
      const operationHours = this.calculateHoursDiff(schedule.open_time, schedule.close_time);
      const actualFlowM3s = adjustedHeight * this.flowCoefficients.manual.flow_per_cm;
      const expectedVolumeM3 = actualFlowM3s * operationHours * 3600;
      
      settings.push({
        gate_id: gate.name,
        gate_type: 'manual',
        gate_location: gate.location,
        opening_height_cm: adjustedHeight,
        open_time: schedule.open_time,
        close_time: schedule.close_time,
        operation_duration_hours: operationHours,
        target_flow_m3s: actualFlowM3s,
        expected_volume_m3: expectedVolumeM3,
        operator_instructions: this.generateOperatorInstructions(gate, adjustedHeight, schedule, priority)
      });
    }
    
    return settings;
  }

  /**
   * Calculate priority based on demand and crop stage
   */
  calculatePriority(sectionDemand, weekNumber) {
    let basePriority = 5;
    
    // Increase priority for critical crop weeks (3-5)
    if (sectionDemand.crop_week >= 3 && sectionDemand.crop_week <= 5) {
      basePriority += 3;
    }
    
    // Increase priority for low water levels
    if (sectionDemand.water_level_status === 'low' || sectionDemand.water_level_avg_cm < 10) {
      basePriority += 2;
    }
    
    // Adjust based on growth stage
    if (sectionDemand.growth_stage === 'flowering' || sectionDemand.growth_stage === 'reproductive') {
      basePriority += 1;
    }
    
    return Math.min(10, basePriority);
  }

  /**
   * Get operational hours based on priority
   */
  getOperationalHours(priority) {
    if (priority >= 8) {
      return this.operationalParams.weekly_hours * this.operationalParams.efficiency_factor;
    } else if (priority >= 6) {
      return this.operationalParams.weekly_hours * 0.75;
    } else {
      return this.operationalParams.weekly_hours * 0.65;
    }
  }

  /**
   * Get automatic gate schedule based on priority and week
   */
  getAutomaticGateSchedule(priority, weekNumber) {
    const schedules = this.operationalParams.gate_operation_schedule.automatic;
    
    // High priority: early start, late end
    if (priority >= 8) {
      return {
        open_time: schedules.start_times[0], // 05:00
        close_time: schedules.end_times[3]    // 21:00
      };
    } 
    // Medium priority: normal hours
    else if (priority >= 6) {
      return {
        open_time: schedules.start_times[1], // 06:00
        close_time: schedules.end_times[2]    // 20:00
      };
    } 
    // Low priority: shorter hours
    else {
      return {
        open_time: schedules.start_times[2], // 07:00
        close_time: schedules.end_times[0]    // 18:00
      };
    }
  }

  /**
   * Get manual gate schedule with variation
   */
  getManualGateSchedule(gateIndex, priority, weekNumber) {
    const baseSchedule = this.operationalParams.gate_operation_schedule.manual;
    
    // Vary schedule based on gate index to distribute workload
    if (gateIndex % 3 === 0) {
      // Morning shift
      return {
        open_time: baseSchedule.morning_shift.start,
        close_time: baseSchedule.morning_shift.end
      };
    } else if (gateIndex % 3 === 1 && priority >= 7) {
      // Full day for high priority
      return {
        open_time: baseSchedule.full_day.start,
        close_time: baseSchedule.full_day.end
      };
    } else {
      // Afternoon shift or adjusted times
      const hourOffset = (weekNumber % 3) - 1; // -1, 0, or 1
      return {
        open_time: this.adjustTime(baseSchedule.afternoon_shift.start, hourOffset),
        close_time: this.adjustTime(baseSchedule.afternoon_shift.end, hourOffset)
      };
    }
  }

  /**
   * Generate operator instructions
   */
  generateOperatorInstructions(gate, openingHeight, schedule, priority) {
    const priorityText = priority >= 8 ? 'HIGH PRIORITY' : priority >= 6 ? 'MEDIUM PRIORITY' : 'NORMAL';
    
    return `${priorityText}: Open gate ${gate.name} to ${openingHeight}cm at ${schedule.open_time}. ` +
           `Close at ${schedule.close_time}. Location: ${gate.location}. ` +
           `Monitor flow rate and adjust if needed.`;
  }

  /**
   * Calculate hours difference between times
   */
  calculateHoursDiff(startTime, endTime) {
    const [startHour, startMin] = startTime.split(':').map(Number);
    const [endHour, endMin] = endTime.split(':').map(Number);
    
    const startMinutes = startHour * 60 + startMin;
    const endMinutes = endHour * 60 + endMin;
    
    return (endMinutes - startMinutes) / 60;
  }

  /**
   * Adjust time by hours
   */
  adjustTime(timeStr, hours) {
    const [hour, minute] = timeStr.split(':').map(Number);
    const newHour = Math.max(0, Math.min(23, hour + hours));
    return `${String(newHour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`;
  }
}

module.exports = HydraulicCalculatorService;