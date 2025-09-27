#!/usr/bin/env node

const { exec } = require('child_process');
const path = require('path');

// Configuration
const EXPORT_SCRIPT = path.join(__dirname, 'export-claude-conversations.sh');
const INTERVAL_MINUTES = 60; // Run every hour

console.log('Claude Conversation Export Service Started');
console.log(`Will export conversations every ${INTERVAL_MINUTES} minutes`);

// Function to run the export
function runExport() {
    const timestamp = new Date().toISOString();
    console.log(`[${timestamp}] Starting conversation export...`);
    
    exec(EXPORT_SCRIPT, (error, stdout, stderr) => {
        if (error) {
            console.error(`[${timestamp}] Export error:`, error);
            return;
        }
        if (stderr) {
            console.error(`[${timestamp}] Export stderr:`, stderr);
        }
        console.log(`[${timestamp}] Export completed successfully`);
        if (stdout) {
            console.log(stdout);
        }
    });
}

// Run immediately on start
runExport();

// Schedule regular runs
setInterval(runExport, INTERVAL_MINUTES * 60 * 1000);

// Keep the process alive
process.on('SIGINT', () => {
    console.log('\nShutting down export service...');
    process.exit(0);
});