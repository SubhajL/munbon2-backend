// Comprehensive Gate-to-Section Mapping for Munbon Irrigation System
// Based on actual irrigation infrastructure with 40-50 control valves

const comprehensiveGateMapping = {
  // Zone 1 (01-01) Gates - Right Main Canal Upper Section
  'RMC1': { 
    zones: ['01-01'], 
    sections: ['01-01-01-01', '01-01-01-02'], 
    type: 'automatic', 
    flowCoeff: 0.025,
    location: 'Right Main Canal Gate 1',
    capacity_cms: 2.5
  },
  'RMC3': { 
    zones: ['01-01'], 
    sections: ['01-01-02-01', '01-01-02-02'], 
    type: 'automatic', 
    flowCoeff: 0.025,
    location: 'Right Main Canal Gate 3',
    capacity_cms: 2.5
  },
  'MG-01-01-A': { 
    zones: ['01-01'], 
    sections: ['01-01-01-01'], 
    type: 'manual',
    location: 'Zone 1 Manual Gate A'
  },
  'MG-01-01-B': { 
    zones: ['01-01'], 
    sections: ['01-01-01-02'], 
    type: 'manual',
    location: 'Zone 1 Manual Gate B'
  },
  'MG-01-01-C': { 
    zones: ['01-01'], 
    sections: ['01-01-02-01'], 
    type: 'manual',
    location: 'Zone 1 Manual Gate C'
  },
  'MG-01-01-D': { 
    zones: ['01-01'], 
    sections: ['01-01-02-02'], 
    type: 'manual',
    location: 'Zone 1 Manual Gate D'
  },

  // Zone 2 (01-02) Gates - Right Main Canal Middle Section
  'RMC2': { 
    zones: ['01-02'], 
    sections: ['01-02-01-01', '01-02-01-02'], 
    type: 'automatic', 
    flowCoeff: 0.025,
    location: 'Right Main Canal Gate 2',
    capacity_cms: 2.5
  },
  '4L-RMC1': { 
    zones: ['01-02'], 
    sections: ['01-02-02-01', '01-02-02-02'], 
    type: 'automatic', 
    flowCoeff: 0.025,
    location: '4L Right Main Canal Gate 1',
    capacity_cms: 2.0
  },
  'MG-01-02-A': { 
    zones: ['01-02'], 
    sections: ['01-02-01-01'], 
    type: 'manual',
    location: 'Zone 2 Manual Gate A'
  },
  'MG-01-02-B': { 
    zones: ['01-02'], 
    sections: ['01-02-01-02'], 
    type: 'manual',
    location: 'Zone 2 Manual Gate B'
  },
  'MG-01-02-C': { 
    zones: ['01-02'], 
    sections: ['01-02-02-01'], 
    type: 'manual',
    location: 'Zone 2 Manual Gate C'
  },
  'MG-01-02-D': { 
    zones: ['01-02'], 
    sections: ['01-02-02-02'], 
    type: 'manual',
    location: 'Zone 2 Manual Gate D'
  },

  // Zone 3 (01-03) Gates - Right Main Canal Lower Section
  'RMC4': { 
    zones: ['01-03'], 
    sections: ['01-03-01-01', '01-03-01-02'], 
    type: 'automatic', 
    flowCoeff: 0.025,
    location: 'Right Main Canal Gate 4',
    capacity_cms: 2.5
  },
  '4L-RMC2': { 
    zones: ['01-03'], 
    sections: ['01-03-02-01'], 
    type: 'automatic', 
    flowCoeff: 0.025,
    location: '4L Right Main Canal Gate 2',
    capacity_cms: 2.0
  },
  '4L-RMC3': { 
    zones: ['01-03'], 
    sections: ['01-03-02-02'], 
    type: 'automatic', 
    flowCoeff: 0.025,
    location: '4L Right Main Canal Gate 3',
    capacity_cms: 2.0
  },
  'MG-01-03-A': { 
    zones: ['01-03'], 
    sections: ['01-03-01-01'], 
    type: 'manual',
    location: 'Zone 3 Manual Gate A'
  },
  'MG-01-03-B': { 
    zones: ['01-03'], 
    sections: ['01-03-01-02'], 
    type: 'manual',
    location: 'Zone 3 Manual Gate B'
  },
  'MG-01-03-C': { 
    zones: ['01-03'], 
    sections: ['01-03-02-01'], 
    type: 'manual',
    location: 'Zone 3 Manual Gate C'
  },
  'MG-01-03-D': { 
    zones: ['01-03'], 
    sections: ['01-03-02-02'], 
    type: 'manual',
    location: 'Zone 3 Manual Gate D'
  },

  // Zone 4 (01-04) Gates - Transition Zone (Right to Left)
  'RMC5': { 
    zones: ['01-04'], 
    sections: ['01-04-01-01'], 
    type: 'automatic', 
    flowCoeff: 0.025,
    location: 'Right Main Canal Gate 5',
    capacity_cms: 2.5
  },
  '4L-RMC5': { 
    zones: ['01-04'], 
    sections: ['01-04-01-02'], 
    type: 'automatic', 
    flowCoeff: 0.025,
    location: '4L Right Main Canal Gate 5',
    capacity_cms: 2.0
  },
  'LMC1': { 
    zones: ['01-04'], 
    sections: ['01-04-02-01', '01-04-02-02'], 
    type: 'automatic', 
    flowCoeff: 0.025,
    location: 'Left Main Canal Gate 1',
    capacity_cms: 2.5
  },
  'MG-01-04-A': { 
    zones: ['01-04'], 
    sections: ['01-04-01-01'], 
    type: 'manual',
    location: 'Zone 4 Manual Gate A'
  },
  'MG-01-04-B': { 
    zones: ['01-04'], 
    sections: ['01-04-01-02'], 
    type: 'manual',
    location: 'Zone 4 Manual Gate B'
  },
  'MG-01-04-C': { 
    zones: ['01-04'], 
    sections: ['01-04-02-01'], 
    type: 'manual',
    location: 'Zone 4 Manual Gate C'
  },
  'MG-01-04-D': { 
    zones: ['01-04'], 
    sections: ['01-04-02-02'], 
    type: 'manual',
    location: 'Zone 4 Manual Gate D'
  },

  // Zone 5 (01-05) Gates - Left Main Canal Upper Section
  'LMC3': { 
    zones: ['01-05'], 
    sections: ['01-05-01-01', '01-05-01-02'], 
    type: 'automatic', 
    flowCoeff: 0.025,
    location: 'Left Main Canal Gate 3',
    capacity_cms: 2.5
  },
  'LMC4': { 
    zones: ['01-05'], 
    sections: ['01-05-02-01', '01-05-02-02'], 
    type: 'automatic', 
    flowCoeff: 0.025,
    location: 'Left Main Canal Gate 4',
    capacity_cms: 2.5
  },
  '4L-LMC1': { 
    zones: ['01-05'], 
    sections: ['01-05-03-01'], 
    type: 'automatic', 
    flowCoeff: 0.025,
    location: '4L Left Main Canal Gate 1',
    capacity_cms: 2.0
  },
  'MG-01-05-A': { 
    zones: ['01-05'], 
    sections: ['01-05-01-01'], 
    type: 'manual',
    location: 'Zone 5 Manual Gate A'
  },
  'MG-01-05-B': { 
    zones: ['01-05'], 
    sections: ['01-05-01-02'], 
    type: 'manual',
    location: 'Zone 5 Manual Gate B'
  },
  'MG-01-05-C': { 
    zones: ['01-05'], 
    sections: ['01-05-02-01'], 
    type: 'manual',
    location: 'Zone 5 Manual Gate C'
  },
  'MG-01-05-D': { 
    zones: ['01-05'], 
    sections: ['01-05-02-02'], 
    type: 'manual',
    location: 'Zone 5 Manual Gate D'
  },
  'MG-01-05-E': { 
    zones: ['01-05'], 
    sections: ['01-05-03-01'], 
    type: 'manual',
    location: 'Zone 5 Manual Gate E'
  },

  // Zone 6 (01-06) Gates - Left Main Canal Lower Section (PREVIOUSLY MISSING!)
  'LMC5': { 
    zones: ['01-06'], 
    sections: ['01-06-01-01', '01-06-01-02'], 
    type: 'automatic', 
    flowCoeff: 0.025,
    location: 'Left Main Canal Gate 5',
    capacity_cms: 2.5
  },
  'LMC6': { 
    zones: ['01-06'], 
    sections: ['01-06-02-01', '01-06-02-02'], 
    type: 'automatic', 
    flowCoeff: 0.025,
    location: 'Left Main Canal Gate 6',
    capacity_cms: 2.5
  },
  '4L-LMC2': { 
    zones: ['01-06'], 
    sections: ['01-06-03-01'], 
    type: 'automatic', 
    flowCoeff: 0.025,
    location: '4L Left Main Canal Gate 2',
    capacity_cms: 2.0
  },
  '4L-LMC3': { 
    zones: ['01-06'], 
    sections: ['01-06-03-02'], 
    type: 'automatic', 
    flowCoeff: 0.025,
    location: '4L Left Main Canal Gate 3',
    capacity_cms: 2.0
  },
  'MG-01-06-A': { 
    zones: ['01-06'], 
    sections: ['01-06-01-01'], 
    type: 'manual',
    location: 'Zone 6 Manual Gate A'
  },
  'MG-01-06-B': { 
    zones: ['01-06'], 
    sections: ['01-06-01-02'], 
    type: 'manual',
    location: 'Zone 6 Manual Gate B'
  },
  'MG-01-06-C': { 
    zones: ['01-06'], 
    sections: ['01-06-02-01'], 
    type: 'manual',
    location: 'Zone 6 Manual Gate C'
  },
  'MG-01-06-D': { 
    zones: ['01-06'], 
    sections: ['01-06-02-02'], 
    type: 'manual',
    location: 'Zone 6 Manual Gate D'
  },
  'MG-01-06-E': { 
    zones: ['01-06'], 
    sections: ['01-06-03-01'], 
    type: 'manual',
    location: 'Zone 6 Manual Gate E'
  },
  'MG-01-06-F': { 
    zones: ['01-06'], 
    sections: ['01-06-03-02'], 
    type: 'manual',
    location: 'Zone 6 Manual Gate F'
  },

  // Shared/Cross-Zone Gates
  'RMC6': { 
    zones: ['01-03', '01-04'], 
    sections: ['01-03-03-01', '01-04-00-01'], 
    type: 'automatic', 
    flowCoeff: 0.025,
    location: 'Right Main Canal Gate 6 (Shared)',
    capacity_cms: 3.0
  },
  '4L-RMC6': { 
    zones: ['01-03', '01-04'], 
    sections: ['01-03-03-02', '01-04-00-02'], 
    type: 'automatic', 
    flowCoeff: 0.025,
    location: '4L Right Main Canal Gate 6 (Shared)',
    capacity_cms: 2.5
  },
  'LMC2': { 
    zones: ['01-04', '01-05'], 
    sections: ['01-04-03-01', '01-05-00-01'], 
    type: 'automatic', 
    flowCoeff: 0.025,
    location: 'Left Main Canal Gate 2 (Shared)',
    capacity_cms: 3.0
  }
};

// Summary statistics
const gateStatistics = {
  totalGates: Object.keys(comprehensiveGateMapping).length,
  automaticGates: Object.values(comprehensiveGateMapping).filter(g => g.type === 'automatic').length,
  manualGates: Object.values(comprehensiveGateMapping).filter(g => g.type === 'manual').length,
  zoneDistribution: {
    '01-01': Object.values(comprehensiveGateMapping).filter(g => g.zones.includes('01-01')).length,
    '01-02': Object.values(comprehensiveGateMapping).filter(g => g.zones.includes('01-02')).length,
    '01-03': Object.values(comprehensiveGateMapping).filter(g => g.zones.includes('01-03')).length,
    '01-04': Object.values(comprehensiveGateMapping).filter(g => g.zones.includes('01-04')).length,
    '01-05': Object.values(comprehensiveGateMapping).filter(g => g.zones.includes('01-05')).length,
    '01-06': Object.values(comprehensiveGateMapping).filter(g => g.zones.includes('01-06')).length
  }
};

// Zone priorities including Zone 6
const zonePriorities = {
  '01-01': { basePriority: 7, criticalWeeks: [3, 4, 5], cropType: 'rice' },
  '01-02': { basePriority: 8, criticalWeeks: [3, 4, 5], cropType: 'rice' },
  '01-03': { basePriority: 9, criticalWeeks: [3, 4, 5], cropType: 'rice' },
  '01-04': { basePriority: 6, criticalWeeks: [3, 4, 5], cropType: 'mixed' },
  '01-05': { basePriority: 7, criticalWeeks: [2, 3, 4], cropType: 'rice' },
  '01-06': { basePriority: 8, criticalWeeks: [2, 3, 4], cropType: 'rice' }
};

// Helper function to get gates by section
function getGatesBySection(sectionId) {
  return Object.entries(comprehensiveGateMapping)
    .filter(([_, config]) => config.sections && config.sections.includes(sectionId))
    .map(([gateName, config]) => ({ name: gateName, ...config }));
}

// Helper function to get gates by zone
function getGatesByZone(zoneId) {
  return Object.entries(comprehensiveGateMapping)
    .filter(([_, config]) => config.zones.includes(zoneId))
    .map(([gateName, config]) => ({ name: gateName, ...config }));
}

module.exports = {
  comprehensiveGateMapping,
  gateStatistics,
  zonePriorities,
  getGatesBySection,
  getGatesByZone
};