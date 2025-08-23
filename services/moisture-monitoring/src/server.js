"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = __importDefault(require("express"));
const dotenv_1 = require("dotenv");
const cors_1 = __importDefault(require("cors"));
const helmet_1 = __importDefault(require("helmet"));
const morgan_1 = __importDefault(require("morgan"));
const error_middleware_1 = require("./middleware/error.middleware");
const moisture_routes_1 = __importDefault(require("./routes/moisture.routes"));
const health_routes_1 = __importDefault(require("./routes/health.routes"));
const tunnel_config_1 = require("./config/tunnel.config");
// Load environment variables
(0, dotenv_1.config)();
const app = (0, express_1.default)();
const PORT = process.env.PORT || 3005;
// Middleware
app.use((0, helmet_1.default)());
app.use((0, cors_1.default)());
app.use((0, morgan_1.default)('combined'));
app.use(express_1.default.json());
app.use(express_1.default.urlencoded({ extended: true }));
// Routes
app.use('/api/v1/moisture', moisture_routes_1.default);
app.use('/health', health_routes_1.default);
// Telemetry endpoint for moisture sensors (legacy support)
app.post('/api/v1/:token/telemetry', (req, res) => {
    // Forward to sensor-data service for processing
    // This is a placeholder - actual implementation would forward to sensor-data service
    console.log(`Received telemetry from token: ${req.params.token}`, req.body);
    res.json({ status: 'received', timestamp: new Date() });
});
// Error handling
app.use(error_middleware_1.errorHandler);
// Start server
app.listen(PORT, () => {
    console.log(`Moisture monitoring service running on port ${PORT}`);
    // Display tunnel configuration if enabled
    if (process.env.TUNNEL_ENABLED === 'true') {
        (0, tunnel_config_1.displayTunnelInfo)();
    }
});
//# sourceMappingURL=server.js.map