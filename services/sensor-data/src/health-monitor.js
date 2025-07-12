const axios = require('axios');
const nodemailer = require('nodemailer');
const { exec } = require('child_process');
const fs = require('fs').promises;
const path = require('path');

class HealthMonitor {
  constructor(config = {}) {
    this.config = {
      tunnelUrl: config.tunnelUrl || 'https://munbon-api.beautifyai.io',
      localApiUrl: config.localApiUrl || 'http://localhost:3000',
      checkInterval: config.checkInterval || 300000, // 5 minutes
      maxRetries: config.maxRetries || 3,
      retryDelay: config.retryDelay || 30000, // 30 seconds
      logFile: config.logFile || path.join(__dirname, '../logs/health-monitor.log'),
      ...config
    };
    
    this.failureCount = {
      tunnel: 0,
      api: 0
    };
    
    this.lastStatus = {
      tunnel: 'unknown',
      api: 'unknown'
    };
  }

  async log(message, level = 'INFO') {
    const timestamp = new Date().toISOString();
    const logEntry = `[${timestamp}] [${level}] ${message}\n`;
    
    console.log(logEntry.trim());
    
    try {
      await fs.appendFile(this.config.logFile, logEntry);
    } catch (error) {
      console.error('Failed to write to log file:', error);
    }
  }

  async checkTunnelHealth() {
    try {
      const response = await axios.get(`${this.config.tunnelUrl}/health`, {
        timeout: 10000,
        validateStatus: () => true,
        headers: {
          'X-Internal-Key': 'munbon-internal-f3b89263126548'
        }
      });
      
      if (response.status === 200 || response.status === 401 || response.status === 404) {
        // 200 = success with auth
        // 401 = tunnel working but no auth (still proves tunnel is up)
        // 404 = tunnel up but endpoint not found
        this.failureCount.tunnel = 0;
        
        if (this.lastStatus.tunnel !== 'up') {
          await this.log(`Tunnel is UP at ${this.config.tunnelUrl}`, 'INFO');
          this.lastStatus.tunnel = 'up';
        }
        
        return true;
      } else {
        throw new Error(`Unexpected status: ${response.status}`);
      }
    } catch (error) {
      this.failureCount.tunnel++;
      
      if (this.lastStatus.tunnel !== 'down') {
        await this.log(`Tunnel is DOWN: ${error.message}`, 'ERROR');
        this.lastStatus.tunnel = 'down';
      }
      
      if (this.failureCount.tunnel >= this.config.maxRetries) {
        await this.handleTunnelFailure();
      }
      
      return false;
    }
  }

  async checkApiHealth() {
    try {
      const response = await axios.get(`${this.config.localApiUrl}/health`, {
        timeout: 10000,
        headers: {
          'X-Internal-Key': 'munbon-internal-f3b89263126548'
        }
      });
      
      if (response.status === 200) {
        this.failureCount.api = 0;
        
        if (this.lastStatus.api !== 'up') {
          await this.log(`Unified API is UP at ${this.config.localApiUrl}`, 'INFO');
          this.lastStatus.api = 'up';
        }
        
        return true;
      } else {
        throw new Error(`Unexpected status: ${response.status}`);
      }
    } catch (error) {
      this.failureCount.api++;
      
      if (this.lastStatus.api !== 'down') {
        await this.log(`Unified API is DOWN: ${error.message}`, 'ERROR');
        this.lastStatus.api = 'down';
      }
      
      if (this.failureCount.api >= this.config.maxRetries) {
        await this.handleApiFailure();
      }
      
      return false;
    }
  }

  async handleTunnelFailure() {
    await this.log('Attempting to restart tunnel via PM2...', 'WARN');
    
    try {
      // Check if tunnel is running in PM2
      const { stdout: listOutput } = await this.execAsync('pm2 list');
      
      if (listOutput.includes('munbon-api-tunnel')) {
        // Restart existing PM2 process
        await this.execAsync('pm2 restart munbon-api-tunnel');
        await this.log('Tunnel restarted via PM2', 'INFO');
      } else {
        // Start tunnel with PM2
        const configPath = path.join(__dirname, '../pm2-permanent-tunnel.json');
        await this.execAsync(`pm2 start ${configPath}`);
        await this.log('Tunnel started via PM2', 'INFO');
      }
      
      // Reset failure count after restart attempt
      this.failureCount.tunnel = 0;
      
      // Wait before next check
      await new Promise(resolve => setTimeout(resolve, this.config.retryDelay));
    } catch (error) {
      await this.log(`Failed to restart tunnel: ${error.message}`, 'ERROR');
      await this.sendAlert('Tunnel Failure', `Failed to restart tunnel after ${this.config.maxRetries} attempts`);
    }
  }

  async handleApiFailure() {
    await this.log('Attempting to restart Unified API via PM2...', 'WARN');
    
    try {
      // Check if API is running in PM2
      const { stdout: listOutput } = await this.execAsync('pm2 list');
      
      if (listOutput.includes('unified-api')) {
        // Restart existing PM2 process
        await this.execAsync('pm2 restart unified-api');
        await this.log('Unified API restarted via PM2', 'INFO');
      } else {
        // Start API with PM2
        const scriptPath = path.join(__dirname, 'unified-api.js');
        await this.execAsync(`pm2 start ${scriptPath} --name unified-api`);
        await this.log('Unified API started via PM2', 'INFO');
      }
      
      // Reset failure count after restart attempt
      this.failureCount.api = 0;
      
      // Wait before next check
      await new Promise(resolve => setTimeout(resolve, this.config.retryDelay));
    } catch (error) {
      await this.log(`Failed to restart API: ${error.message}`, 'ERROR');
      await this.sendAlert('API Failure', `Failed to restart Unified API after ${this.config.maxRetries} attempts`);
    }
  }

  async sendAlert(subject, message) {
    // Log the alert
    await this.log(`ALERT: ${subject} - ${message}`, 'ERROR');
    
    // If email is configured, send email
    if (this.config.email && this.config.email.enabled) {
      try {
        const transporter = nodemailer.createTransport(this.config.email.smtp);
        
        await transporter.sendMail({
          from: this.config.email.from,
          to: this.config.email.to,
          subject: `[Munbon Monitor] ${subject}`,
          text: message,
          html: `<p>${message}</p><p>Time: ${new Date().toISOString()}</p>`
        });
        
        await this.log('Alert email sent', 'INFO');
      } catch (error) {
        await this.log(`Failed to send email alert: ${error.message}`, 'ERROR');
      }
    }
    
    // If webhook is configured, send webhook
    if (this.config.webhook && this.config.webhook.enabled) {
      try {
        await axios.post(this.config.webhook.url, {
          subject,
          message,
          timestamp: new Date().toISOString(),
          service: 'munbon-health-monitor'
        });
        
        await this.log('Alert webhook sent', 'INFO');
      } catch (error) {
        await this.log(`Failed to send webhook alert: ${error.message}`, 'ERROR');
      }
    }
  }

  execAsync(command) {
    return new Promise((resolve, reject) => {
      exec(command, (error, stdout, stderr) => {
        if (error) {
          reject(error);
        } else {
          resolve({ stdout, stderr });
        }
      });
    });
  }

  async getStatus() {
    const tunnelHealthy = await this.checkTunnelHealth();
    const apiHealthy = await this.checkApiHealth();
    
    return {
      timestamp: new Date().toISOString(),
      services: {
        tunnel: {
          status: tunnelHealthy ? 'up' : 'down',
          url: this.config.tunnelUrl,
          failureCount: this.failureCount.tunnel
        },
        api: {
          status: apiHealthy ? 'up' : 'down',
          url: this.config.localApiUrl,
          failureCount: this.failureCount.api
        }
      }
    };
  }

  async start() {
    await this.log('Health Monitor starting...', 'INFO');
    
    // Initial check
    await this.getStatus();
    
    // Set up interval
    this.interval = setInterval(async () => {
      await this.getStatus();
    }, this.config.checkInterval);
    
    await this.log(`Health Monitor started - checking every ${this.config.checkInterval / 1000} seconds`, 'INFO');
  }

  stop() {
    if (this.interval) {
      clearInterval(this.interval);
      this.log('Health Monitor stopped', 'INFO');
    }
  }
}

module.exports = HealthMonitor;