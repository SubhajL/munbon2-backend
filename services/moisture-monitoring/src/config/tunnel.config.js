"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.tunnelConfig = void 0;
exports.getTunnelUrl = getTunnelUrl;
exports.displayTunnelInfo = displayTunnelInfo;
const dotenv_1 = require("dotenv");
// Load environment variables
(0, dotenv_1.config)();
exports.tunnelConfig = {
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
function getTunnelUrl(endpoint) {
    return `${exports.tunnelConfig.publicUrl}${exports.tunnelConfig.endpoints[endpoint]}`;
}
// Export function to display tunnel info
function displayTunnelInfo() {
    console.log('\n🌱 Moisture Tunnel Configuration');
    console.log('=================================');
    console.log(`Public URL: ${exports.tunnelConfig.publicUrl}`);
    console.log(`Health Check: ${exports.tunnelConfig.healthCheckUrl}`);
    console.log(`Local Port: ${exports.tunnelConfig.localPort}`);
    console.log('\n📡 Public Endpoints:');
    Object.entries(exports.tunnelConfig.endpoints).forEach(([name, path]) => {
        console.log(`  ${name}: ${exports.tunnelConfig.publicUrl}${path}`);
    });
    console.log('=================================\n');
}
//# sourceMappingURL=tunnel.config.js.map