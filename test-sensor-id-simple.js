// Test sensor ID conversion logic
const testCases = [
  { input: '2216617412385143', desc: 'Numeric sensor ID 1' },
  { input: '222410831183230', desc: 'Numeric sensor ID 2' },
  { input: 'AWD-B7E6', desc: 'Already formatted' },
  { input: '00:11:22:33:44:55', desc: 'MAC address' },
];

function formatWaterLevelSensorId(sensorIdOrMac) {
  if (!sensorIdOrMac || sensorIdOrMac.length < 4) {
    throw new Error('Invalid sensor ID or MAC address for formatting');
  }
  
  // If already in AWD format, return as is
  if (sensorIdOrMac.startsWith('AWD-')) {
    return sensorIdOrMac;
  }
  
  // Check if it's a numeric sensor ID (like "2216617412385143")
  if (/^\d+$/.test(sensorIdOrMac)) {
    // Convert numeric ID to hex and take last 4 chars
    const hex = BigInt(sensorIdOrMac).toString(16).toUpperCase();
    const last4 = hex.slice(-4).padStart(4, '0');
    return `AWD-${last4}`;
  }
  
  // Otherwise treat as MAC address - get last 4 characters
  const last4 = sensorIdOrMac.slice(-4).toUpperCase();
  
  return `AWD-${last4}`;
}

console.log('Testing sensor ID formatting...\n');

testCases.forEach(test => {
  try {
    const result = formatWaterLevelSensorId(test.input);
    const hex = /^\d+$/.test(test.input) ? 
      `(hex: ${BigInt(test.input).toString(16).toUpperCase()})` : '';
    console.log(`${test.desc}: ${test.input} ${hex}`);
    console.log(`Result: ${result}\n`);
  } catch (error) {
    console.log(`${test.desc}: ${test.input}`);
    console.log(`Error: ${error.message}\n`);
  }
});