import { config } from 'dotenv';

// Load environment variables
config();

export interface TunnelConfig {
  publicUrl: string;
  healthCheckUrl: string;
  localPort: number;
  endpoints: {
    telemetry: string;
    current: string;
    history: string;
    alerts: string;
    profile: string;
    irrigation: string;
  };
}

export const tunnelConfig: TunnelConfig = {
  // Public URL for the moisture tunnel
  publicUrl: process.env.TUNNEL_PUBLIC_URL || 'https://munbon-moisture.beautifyai.io',
  
  // Health check URL
  healthCheckUrl: process.env.TUNNEL_HEALTH_URL || 'https://munbon-moisture-health.beautifyai.io/health',
  
  // Local port the service runs on
  localPort: parseInt(process.env.PORT || '3005', 10),
  
  // Public endpoints accessible via tunnel
  endpoints: {
    // Telemetry ingestion endpoint for sensors
    telemetry: '/api/v1/munbon-m2m-moisture/telemetry',
    
    // Current moisture readings
    current: '/api/v1/moisture/current',
    
    // Historical data
    history: '/api/v1/moisture/history',
    
    // Moisture alerts
    alerts: '/api/v1/moisture/alerts',
    
    // Moisture profile by depth
    profile: '/api/v1/moisture/profile',
    
    // Irrigation recommendations
    irrigation: '/api/v1/moisture/irrigation'
  }
};

// Export helper function to get full URLs
export function getTunnelUrl(endpoint: keyof typeof tunnelConfig.endpoints): string {
  return `${tunnelConfig.publicUrl}${tunnelConfig.endpoints[endpoint]}`;
}

// Export function to display tunnel info
export function displayTunnelInfo(): void {
  console.log('\n🌱 Moisture Tunnel Configuration');
  console.log('=================================');
  console.log(`Public URL: ${tunnelConfig.publicUrl}`);
  console.log(`Health Check: ${tunnelConfig.healthCheckUrl}`);
  console.log(`Local Port: ${tunnelConfig.localPort}`);
  console.log('\n📡 Public Endpoints:');
  Object.entries(tunnelConfig.endpoints).forEach(([name, path]) => {
    console.log(`  ${name}: ${tunnelConfig.publicUrl}${path}`);
  });
  console.log('=================================\n');
}