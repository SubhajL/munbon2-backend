#!/usr/bin/env node

const HealthMonitor = require('./health-monitor');
const fs = require('fs').promises;
const path = require('path');

// Default configuration
const defaultConfig = {
  tunnelUrl: 'https://munbon-api.beautifyai.io',
  localApiUrl: 'http://localhost:3000',
  checkInterval: 300000, // 5 minutes
  maxRetries: 3,
  retryDelay: 30000, // 30 seconds
  email: {
    enabled: false,
    smtp: {
      host: 'smtp.gmail.com',
      port: 587,
      secure: false,
      auth: {
        user: process.env.SMTP_USER,
        pass: process.env.SMTP_PASS
      }
    },
    from: 'munbon-monitor@example.com',
    to: 'admin@example.com'
  },
  webhook: {
    enabled: false,
    url: process.env.WEBHOOK_URL || 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL'
  }
};

async function loadConfig() {
  const configPath = path.join(__dirname, '../config/health-monitor.json');
  
  try {
    const configData = await fs.readFile(configPath, 'utf8');
    const userConfig = JSON.parse(configData);
    return { ...defaultConfig, ...userConfig };
  } catch (error) {
    console.log('No config file found, using defaults');
    return defaultConfig;
  }
}

async function main() {
  console.log('Starting Munbon Health Monitor...');
  
  const config = await loadConfig();
  const monitor = new HealthMonitor(config);
  
  // Handle shutdown gracefully
  process.on('SIGINT', () => {
    console.log('\nShutting down health monitor...');
    monitor.stop();
    process.exit(0);
  });
  
  process.on('SIGTERM', () => {
    console.log('\nShutting down health monitor...');
    monitor.stop();
    process.exit(0);
  });
  
  // Start monitoring
  await monitor.start();
}

main().catch(error => {
  console.error('Failed to start health monitor:', error);
  process.exit(1);
});