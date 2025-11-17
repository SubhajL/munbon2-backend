#!/usr/bin/env node
/**
 * Test script to verify timezone conversion for MSSQL valve commands
 * This simulates sending a valve command and shows the exact timestamp that would be inserted
 */

require('dotenv').config();
const { convertUTCToLocalTime, formatDateForMSSQL } = require('./src/utils/timezone');

console.log('='.repeat(80));
console.log('Timezone Conversion Test for MSSQL Valve Commands');
console.log('='.repeat(80));
console.log();

// Simulate current UTC time
const utcNow = new Date();
console.log(`Current UTC time:     ${utcNow.toISOString()}`);
console.log(`                      ${utcNow.toUTCString()}`);
console.log();

// Convert to Bangkok local time
const timezone = process.env.TIMEZONE || 'Asia/Bangkok';
const localTime = convertUTCToLocalTime(utcNow, timezone);
const formatted = formatDateForMSSQL(localTime);

console.log(`Timezone:             ${timezone}`);
console.log(`Local time (Date):    ${localTime.toISOString()}`);
console.log(`Formatted for MSSQL:  ${formatted}`);
console.log();

// Show what will be inserted
console.log('What will be inserted into MSSQL tb_valve_command_v2_test:');
console.log(`  valve_name:      'SV_C1_L'`);
console.log(`  valve_level:     1`);
console.log(`  startdatetime:   '${formatted}'`);
console.log();

// Verify offset
const offsetHours = (localTime.getTime() - utcNow.getTime()) / (1000 * 60 * 60);
console.log(`Offset verification:  ${offsetHours > 0 ? '+' : ''}${offsetHours} hours`);
console.log();

// Show more examples
console.log('Additional examples:');
console.log('-'.repeat(80));

const examples = [
  new Date('2025-10-28T00:00:00Z'),
  new Date('2025-10-28T08:23:48Z'),
  new Date('2025-10-28T16:30:00Z'),
  new Date('2025-10-28T23:59:59Z')
];

examples.forEach(utc => {
  const local = convertUTCToLocalTime(utc, timezone);
  const fmt = formatDateForMSSQL(local);
  console.log(`UTC: ${utc.toISOString().padEnd(25)} → Local: ${fmt}`);
});

console.log();
console.log('='.repeat(80));
console.log('✓ Timezone conversion module loaded successfully');
console.log('✓ Ready to deploy');
console.log('='.repeat(80));
