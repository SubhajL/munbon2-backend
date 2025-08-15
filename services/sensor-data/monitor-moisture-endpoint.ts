import * as fs from 'fs';
import * as path from 'path';
import { format } from 'date-fns';

interface MoistureDataLog {
  timestamp: Date;
  gatewayId: string;
  sensorCount: number;
  sensors: Array<{
    id: string;
    surface: number;
    deep: number;
  }>;
  sourceIp?: string;
}

class MoistureEndpointMonitor {
  private logFile: string;
  private statsFile: string;
  private lastCheckFile: string;
  
  constructor() {
    const logsDir = path.join(__dirname, 'logs', 'moisture-monitor');
    if (!fs.existsSync(logsDir)) {
      fs.mkdirSync(logsDir, { recursive: true });
    }
    
    const today = format(new Date(), 'yyyy-MM-dd');
    this.logFile = path.join(logsDir, `moisture-data-${today}.log`);
    this.statsFile = path.join(logsDir, 'moisture-stats.json');
    this.lastCheckFile = path.join(logsDir, 'last-check.txt');
  }
  
  async checkRemoteLogs(sshKeyPath: string, ec2Host: string): Promise<void> {
    const { exec } = require('child_process');
    const util = require('util');
    const execPromise = util.promisify(exec);
    
    try {
      // Get the last 100 lines of moisture HTTP logs
      const command = `ssh -i ${sshKeyPath} ubuntu@${ec2Host} "tail -100 /home/ubuntu/.pm2/logs/moisture-http-out.log | grep -A20 'Received moisture'"`;
      
      const { stdout } = await execPromise(command);
      
      if (stdout) {
        const entries = this.parseLogEntries(stdout);
        this.saveEntries(entries);
        this.updateStats(entries);
        console.log(`Found ${entries.length} moisture data entries`);
        
        // Show summary
        if (entries.length > 0) {
          console.log('\nLatest moisture data:');
          const latest = entries[entries.length - 1];
          console.log(`- Time: ${latest.timestamp}`);
          console.log(`- Gateway: ${latest.gatewayId}`);
          console.log(`- Sensors: ${latest.sensorCount}`);
          latest.sensors.forEach(s => {
            console.log(`  - Sensor ${s.id}: Surface=${s.surface}%, Deep=${s.deep}%`);
          });
        }
      } else {
        console.log('No moisture data found in recent logs');
      }
      
      // Update last check time
      fs.writeFileSync(this.lastCheckFile, new Date().toISOString());
      
    } catch (error) {
      console.error('Error checking remote logs:', error);
    }
  }
  
  private parseLogEntries(logOutput: string): MoistureDataLog[] {
    const entries: MoistureDataLog[] = [];
    const lines = logOutput.split('\n');
    
    let currentEntry: any = null;
    let inDataBlock = false;
    let dataBuffer = '';
    
    for (const line of lines) {
      if (line.includes('Received moisture data via HTTP')) {
        // Start of new entry
        const timestampMatch = line.match(/\[(\d+:\d+:\d+\.\d+)\]/);
        if (timestampMatch) {
          const [hours, minutes, seconds] = timestampMatch[1].split(':');
          const now = new Date();
          now.setHours(parseInt(hours), parseInt(minutes), parseInt(seconds));
          currentEntry = { timestamp: now };
        }
        inDataBlock = true;
        dataBuffer = '';
      } else if (inDataBlock && line.includes('data: {')) {
        dataBuffer = '{';
      } else if (inDataBlock && dataBuffer) {
        dataBuffer += line + '\n';
        if (line.trim() === '}') {
          // End of data block
          try {
            const data = JSON.parse(dataBuffer);
            currentEntry.gatewayId = data.gw_id;
            currentEntry.sensors = [];
            
            if (data.sensor && Array.isArray(data.sensor)) {
              currentEntry.sensorCount = data.sensor.length;
              data.sensor.forEach((s: any) => {
                currentEntry.sensors.push({
                  id: s.sensor_id,
                  surface: parseFloat(s.humid_hi) || 0,
                  deep: parseFloat(s.humid_low) || 0
                });
              });
            } else {
              currentEntry.sensorCount = 0;
            }
            
            entries.push(currentEntry);
            inDataBlock = false;
            dataBuffer = '';
          } catch (e) {
            // Skip malformed entries
          }
        }
      }
    }
    
    return entries;
  }
  
  private saveEntries(entries: MoistureDataLog[]): void {
    const logData = entries.map(e => 
      `${e.timestamp.toISOString()},${e.gatewayId},${e.sensorCount},${JSON.stringify(e.sensors)}`
    ).join('\n');
    
    if (logData) {
      fs.appendFileSync(this.logFile, logData + '\n');
    }
  }
  
  private updateStats(entries: MoistureDataLog[]): void {
    let stats: any = {};
    
    if (fs.existsSync(this.statsFile)) {
      stats = JSON.parse(fs.readFileSync(this.statsFile, 'utf-8'));
    }
    
    const today = format(new Date(), 'yyyy-MM-dd');
    if (!stats[today]) {
      stats[today] = {
        totalMessages: 0,
        gateways: {},
        sensors: {},
        hourlyCount: {}
      };
    }
    
    entries.forEach(entry => {
      stats[today].totalMessages++;
      
      // Track gateways
      if (!stats[today].gateways[entry.gatewayId]) {
        stats[today].gateways[entry.gatewayId] = 0;
      }
      stats[today].gateways[entry.gatewayId]++;
      
      // Track sensors
      entry.sensors.forEach(sensor => {
        const sensorId = `${entry.gatewayId}-${sensor.id}`;
        if (!stats[today].sensors[sensorId]) {
          stats[today].sensors[sensorId] = {
            count: 0,
            avgSurface: 0,
            avgDeep: 0,
            values: []
          };
        }
        
        const sensorStats = stats[today].sensors[sensorId];
        sensorStats.count++;
        sensorStats.values.push({
          surface: sensor.surface,
          deep: sensor.deep,
          time: entry.timestamp
        });
        
        // Keep only last 10 values
        if (sensorStats.values.length > 10) {
          sensorStats.values = sensorStats.values.slice(-10);
        }
        
        // Calculate averages
        const surfaces = sensorStats.values.map((v: any) => v.surface);
        const deeps = sensorStats.values.map((v: any) => v.deep);
        sensorStats.avgSurface = surfaces.reduce((a: number, b: number) => a + b, 0) / surfaces.length;
        sensorStats.avgDeep = deeps.reduce((a: number, b: number) => a + b, 0) / deeps.length;
      });
      
      // Track hourly
      const hour = format(entry.timestamp, 'HH');
      if (!stats[today].hourlyCount[hour]) {
        stats[today].hourlyCount[hour] = 0;
      }
      stats[today].hourlyCount[hour]++;
    });
    
    fs.writeFileSync(this.statsFile, JSON.stringify(stats, null, 2));
  }
  
  showStats(): void {
    if (!fs.existsSync(this.statsFile)) {
      console.log('No stats available yet');
      return;
    }
    
    const stats = JSON.parse(fs.readFileSync(this.statsFile, 'utf-8'));
    const today = format(new Date(), 'yyyy-MM-dd');
    
    if (stats[today]) {
      console.log(`\nMoisture Data Statistics for ${today}:`);
      console.log(`- Total messages: ${stats[today].totalMessages}`);
      console.log(`- Active gateways: ${Object.keys(stats[today].gateways).length}`);
      console.log(`- Active sensors: ${Object.keys(stats[today].sensors).length}`);
      
      console.log('\nGateway message counts:');
      Object.entries(stats[today].gateways).forEach(([gw, count]) => {
        console.log(`  - ${gw}: ${count} messages`);
      });
      
      console.log('\nHourly distribution:');
      Object.entries(stats[today].hourlyCount)
        .sort(([a], [b]) => a.localeCompare(b))
        .forEach(([hour, count]) => {
          console.log(`  - ${hour}:00: ${count} messages`);
        });
    }
    
    if (fs.existsSync(this.lastCheckFile)) {
      const lastCheck = fs.readFileSync(this.lastCheckFile, 'utf-8');
      console.log(`\nLast checked: ${lastCheck}`);
    }
  }
}

// Usage
const monitor = new MoistureEndpointMonitor();
const sshKeyPath = '/Users/subhajlimanond/dev/th-lab01.pem';
const ec2Host = '43.209.22.250';

// Run check
monitor.checkRemoteLogs(sshKeyPath, ec2Host).then(() => {
  monitor.showStats();
});

// Export for use as module
export { MoistureEndpointMonitor };