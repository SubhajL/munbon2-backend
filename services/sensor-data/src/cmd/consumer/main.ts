import * as dotenv from 'dotenv';
import { SQSClient, ReceiveMessageCommand, DeleteMessageCommand } from '@aws-sdk/client-sqs';
import express from 'express';
import { createServer } from 'http';
import { Server } from 'socket.io';
import * as fs from 'fs';
import * as path from 'path';
import pino from 'pino';
import { TimescaleRepository } from '../../repository/timescale.repository';
import { processIncomingData } from '../../services/sqs-processor';

dotenv.config();

const logger = pino({
  transport: {
    target: 'pino-pretty',
    options: {
      colorize: true
    }
  }
});

// Statistics tracking
interface ConsumerStats {
  messagesReceived: number;
  messagesProcessed: number;
  messagesFailed: number;
  lastMessageTime: string | null;
  startTime: string;
  sensorTypes: Record<string, number>;
  sensorIds: Set<string>;
}

const stats: ConsumerStats = {
  messagesReceived: 0,
  messagesProcessed: 0,
  messagesFailed: 0,
  lastMessageTime: null,
  startTime: new Date().toISOString(),
  sensorTypes: {},
  sensorIds: new Set()
};

// AWS SQS Configuration
const sqsClient = new SQSClient({
  region: process.env.AWS_REGION || 'ap-southeast-1',
  credentials: {
    accessKeyId: process.env.AWS_ACCESS_KEY_ID!,
    secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY!
  }
});

// Express app for dashboard
const app = express();
const server = createServer(app);
const io = new Server(server, {
  cors: {
    origin: '*',
    methods: ['GET', 'POST']
  }
});

// Recent sensor data storage
const recentData: any[] = [];
const MAX_RECENT_DATA = 100;

// TimescaleDB repository
let timescaleRepo: TimescaleRepository;

// Process telemetry data
async function processTelemetryData(data: any): Promise<void> {
  stats.messagesReceived++;
  stats.lastMessageTime = new Date().toISOString();
  
  try {
    // Process and save to TimescaleDB
    await processIncomingData(timescaleRepo, data, logger);
    
    // Track sensor types and IDs
    if (data.sensorType) {
      stats.sensorTypes[data.sensorType] = (stats.sensorTypes[data.sensorType] || 0) + 1;
    }
    stats.sensorIds.add(data.sensorId);
    
    // Display based on sensor type
    logger.info({
      sensorType: data.sensorType,
      sensorId: data.sensorId,
      tokenGroup: data.tokenGroup,
      timestamp: data.timestamp
    }, '📡 New Telemetry Data');
    
    // Process based on sensor type
    switch(data.sensorType) {
      case 'water-level':
        logger.info({
          waterLevel: `${data.data.level} cm`,
          voltage: `${data.data.voltage / 100}V`,
          rssi: data.data.RSSI,
          location: data.location
        }, '💧 Water Level Data');
        break;
        
      case 'moisture':
        logger.info({
          moistureSurface: `${data.data.humid_hi}%`,
          moistureDeep: `${data.data.humid_low}%`,
          tempSurface: `${data.data.temp_hi}°C`,
          tempDeep: `${data.data.temp_low}°C`,
          flood: data.data.flood,
          location: data.location
        }, '🌱 Moisture Data');
        break;
        
      default:
        logger.info({ data: data.data }, 'Unknown Sensor Data');
    }
    
    // Store recent data
    recentData.unshift(data);
    if (recentData.length > MAX_RECENT_DATA) {
      recentData.pop();
    }
    
    // Emit to connected websocket clients
    io.emit('sensorData', data);
    
    // Save to file for backup
    const date = new Date().toISOString().split('T')[0];
    const filename = `telemetry_${data.sensorType}_${date}.jsonl`;
    const filepath = path.join(__dirname, '../../../data', filename);
    
    // Ensure data directory exists
    const dataDir = path.dirname(filepath);
    if (!fs.existsSync(dataDir)) {
      fs.mkdirSync(dataDir, { recursive: true });
    }
    
    fs.appendFileSync(filepath, JSON.stringify(data) + '\n');
    
    stats.messagesProcessed++;
  } catch (error) {
    logger.error({ error, data }, 'Failed to process telemetry data');
    stats.messagesFailed++;
    throw error; // Re-throw to prevent message deletion
  }
}

// Poll SQS for messages
async function pollSQS(): Promise<void> {
  const queueUrl = process.env.SQS_QUEUE_URL;
  
  if (!queueUrl) {
    logger.error('SQS_QUEUE_URL not configured');
    return;
  }
  
  try {
    const command = new ReceiveMessageCommand({
      QueueUrl: queueUrl,
      MaxNumberOfMessages: 10,
      WaitTimeSeconds: 20, // Long polling
      VisibilityTimeout: 30
    });
    
    const response = await sqsClient.send(command);
    
    if (response.Messages && response.Messages.length > 0) {
      logger.info(`Received ${response.Messages.length} messages from SQS`);
      
      for (const message of response.Messages) {
        let messageProcessedSuccessfully = false;
        
        try {
          if (message.Body) {
            const telemetryData = JSON.parse(message.Body);
            
            // Process the telemetry data - this will throw if DB write fails
            await processTelemetryData(telemetryData);
            
            // Mark as successful only if no exceptions were thrown
            messageProcessedSuccessfully = true;
            logger.debug({ 
              messageId: message.MessageId,
              sensorId: telemetryData.sensorId 
            }, 'Message processed successfully');
          }
        } catch (error) {
          logger.error({ 
            error, 
            message: message.Body,
            messageId: message.MessageId 
          }, 'Error processing message - will retry');
          stats.messagesFailed++;
        }
        
        // Only delete message if it was processed successfully
        if (messageProcessedSuccessfully && message.ReceiptHandle) {
          try {
            await sqsClient.send(new DeleteMessageCommand({
              QueueUrl: queueUrl,
              ReceiptHandle: message.ReceiptHandle
            }));
            logger.debug({ 
              messageId: message.MessageId 
            }, 'Message deleted from SQS');
          } catch (deleteError) {
            logger.error({ 
              error: deleteError,
              messageId: message.MessageId 
            }, 'Failed to delete message from SQS');
          }
        }
      }
    }
  } catch (error) {
    logger.error({ error }, 'Error polling SQS');
  }
}

// Continuous polling
async function startPolling(): Promise<void> {
  logger.info('🚀 Starting SQS consumer...');
  
  while (true) {
    await pollSQS();
    // Small delay between polls
    await new Promise(resolve => setTimeout(resolve, 100));
  }
}

// Dashboard routes
app.use(express.static(path.join(__dirname, '../../../public')));

app.get('/api/stats', (_req, res) => {
  res.json({
    ...stats,
    sensorCount: stats.sensorIds.size,
    uptime: Date.now() - new Date(stats.startTime).getTime()
  });
});

app.get('/api/recent', (req, res) => {
  const limit = parseInt(req.query.limit as string) || 20;
  res.json(recentData.slice(0, limit));
});

app.get('/api/sensors', (_req, res) => {
  const sensors = Array.from(stats.sensorIds).map(id => {
    const latestData = recentData.find(d => d.sensorId === id);
    return {
      id,
      type: latestData?.sensorType || 'unknown',
      lastSeen: latestData?.timestamp || null,
      location: latestData?.location || null
    };
  });
  res.json(sensors);
});

// Main dashboard page
app.get('/', (_req, res) => {
  const html = `
<!DOCTYPE html>
<html>
<head>
    <title>Munbon IoT Sensor Dashboard</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f5f5;
            padding: 20px;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        h1 { color: #333; margin-bottom: 20px; }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .stat-card h3 { 
            color: #666; 
            font-size: 14px; 
            font-weight: normal;
            margin-bottom: 8px;
        }
        .stat-card .value { 
            font-size: 32px; 
            font-weight: bold;
            color: #333;
        }
        .sensor-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 30px;
        }
        .sensor-card {
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .sensor-card h2 {
            font-size: 20px;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .water-level { border-left: 4px solid #2196F3; }
        .moisture { border-left: 4px solid #4CAF50; }
        .sensor-list {
            max-height: 400px;
            overflow-y: auto;
        }
        .sensor-item {
            padding: 12px;
            border-bottom: 1px solid #eee;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .sensor-item:last-child { border-bottom: none; }
        .sensor-id { font-weight: 500; }
        .sensor-value { 
            font-size: 18px; 
            font-weight: bold;
            color: #333;
        }
        .sensor-meta {
            font-size: 12px;
            color: #666;
            margin-top: 4px;
        }
        .live-indicator {
            display: inline-block;
            width: 8px;
            height: 8px;
            background: #4CAF50;
            border-radius: 50%;
            margin-right: 8px;
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        .no-data { 
            color: #999; 
            text-align: center; 
            padding: 40px;
        }
    </style>
    <script src="/socket.io/socket.io.js"></script>
</head>
<body>
    <div class="container">
        <h1>🏭 Munbon IoT Sensor Dashboard</h1>
        
        <div class="stats-grid">
            <div class="stat-card">
                <h3>Total Messages</h3>
                <div class="value" id="totalMessages">0</div>
            </div>
            <div class="stat-card">
                <h3>Active Sensors</h3>
                <div class="value" id="activeSensors">0</div>
            </div>
            <div class="stat-card">
                <h3>Water Level Sensors</h3>
                <div class="value" id="waterLevelCount">0</div>
            </div>
            <div class="stat-card">
                <h3>Moisture Sensors</h3>
                <div class="value" id="moistureCount">0</div>
            </div>
        </div>
        
        <div class="sensor-grid">
            <div class="sensor-card water-level">
                <h2><span class="live-indicator"></span>💧 Water Level Sensors</h2>
                <div id="waterLevelList" class="sensor-list">
                    <div class="no-data">Waiting for sensor data...</div>
                </div>
            </div>
            
            <div class="sensor-card moisture">
                <h2><span class="live-indicator"></span>🌱 Moisture Sensors</h2>
                <div id="moistureList" class="sensor-list">
                    <div class="no-data">Waiting for sensor data...</div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        const socket = io();
        const waterLevelData = new Map();
        const moistureData = new Map();
        
        async function updateStats() {
            const response = await fetch('/api/stats');
            const stats = await response.json();
            
            document.getElementById('totalMessages').textContent = stats.messagesReceived;
            document.getElementById('activeSensors').textContent = stats.sensorCount;
            document.getElementById('waterLevelCount').textContent = stats.sensorTypes['water-level'] || 0;
            document.getElementById('moistureCount').textContent = stats.sensorTypes['moisture'] || 0;
        }
        
        function formatTime(timestamp) {
            return new Date(timestamp).toLocaleTimeString();
        }
        
        function updateSensorList(containerId, dataMap, sensorType) {
            const container = document.getElementById(containerId);
            if (dataMap.size === 0) {
                container.innerHTML = '<div class="no-data">Waiting for sensor data...</div>';
                return;
            }
            
            const items = Array.from(dataMap.values())
                .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
                .slice(0, 10);
            
            container.innerHTML = items.map(data => {
                let valueHtml = '';
                if (sensorType === 'water-level') {
                    valueHtml = \`<div class="sensor-value">\${data.data.level} cm</div>\`;
                } else if (sensorType === 'moisture') {
                    valueHtml = \`<div class="sensor-value">\${data.data.humid_hi}% / \${data.data.humid_low}%</div>\`;
                }
                
                return \`
                    <div class="sensor-item">
                        <div>
                            <div class="sensor-id">\${data.sensorId}</div>
                            <div class="sensor-meta">
                                \${formatTime(data.timestamp)}
                                \${data.location ? \` • \${data.location.lat.toFixed(4)}, \${data.location.lng.toFixed(4)}\` : ''}
                            </div>
                        </div>
                        \${valueHtml}
                    </div>
                \`;
            }).join('');
        }
        
        socket.on('sensorData', (data) => {
            if (data.sensorType === 'water-level') {
                waterLevelData.set(data.sensorId, data);
                updateSensorList('waterLevelList', waterLevelData, 'water-level');
            } else if (data.sensorType === 'moisture') {
                moistureData.set(data.sensorId, data);
                updateSensorList('moistureList', moistureData, 'moisture');
            }
            updateStats();
        });
        
        // Initial load
        updateStats();
        setInterval(updateStats, 5000);
        
        // Load recent data
        fetch('/api/recent?limit=50')
            .then(res => res.json())
            .then(recent => {
                recent.forEach(data => {
                    if (data.sensorType === 'water-level') {
                        waterLevelData.set(data.sensorId, data);
                    } else if (data.sensorType === 'moisture') {
                        moistureData.set(data.sensorId, data);
                    }
                });
                updateSensorList('waterLevelList', waterLevelData, 'water-level');
                updateSensorList('moistureList', moistureData, 'moisture');
            });
    </script>
</body>
</html>
  `;
  res.send(html);
});

// Start server and polling
const PORT = process.env.CONSUMER_PORT || 3002;

async function start() {
  try {
    // Initialize TimescaleDB connection
    timescaleRepo = new TimescaleRepository({
      host: process.env.TIMESCALE_HOST || 'localhost',
      port: parseInt(process.env.TIMESCALE_PORT || '5433'),
      database: process.env.TIMESCALE_DB || 'munbon_timescale',
      user: process.env.TIMESCALE_USER || 'postgres',
      password: process.env.TIMESCALE_PASSWORD || ''
    });

    await timescaleRepo.initialize();
    logger.info('✅ Connected to TimescaleDB');

    // Start HTTP server
    server.listen(PORT, () => {
      logger.info(`📊 Dashboard running at http://localhost:${PORT}`);
      logger.info('🔄 Starting SQS polling...');
      
      // Start polling in background
      startPolling().catch(error => {
        logger.error({ error }, 'Fatal error in polling');
        process.exit(1);
      });
    });
  } catch (error) {
    logger.error({ error }, 'Failed to start consumer');
    process.exit(1);
  }
}

// Graceful shutdown
process.on('SIGTERM', async () => {
  logger.info('SIGTERM received, shutting down gracefully...');
  
  if (timescaleRepo) {
    await timescaleRepo.close();
  }
  
  server.close(() => {
    logger.info('Server closed');
    process.exit(0);
  });
});

start();