// Check actual sensor ID conversions from the database
const sensorIds = [
  '2216617412385143',
  '222410831183230'
];

console.log('Checking numeric sensor ID conversions:\n');

sensorIds.forEach(id => {
  const bigIntId = BigInt(id);
  const hex = bigIntId.toString(16).toUpperCase();
  const last4 = hex.slice(-4).padStart(4, '0');
  
  console.log(`Numeric ID: ${id}`);
  console.log(`Full hex: ${hex}`);
  console.log(`Last 4 hex: ${last4}`);
  console.log(`AWD format: AWD-${last4}`);
  console.log('---');
});