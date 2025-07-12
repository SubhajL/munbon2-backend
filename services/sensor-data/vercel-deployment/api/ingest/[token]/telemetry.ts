import type { VercelRequest, VercelResponse } from '@vercel/node';

// Token validation
const VALID_TOKENS: Record<string, string> = {
  'munbon-ridr-water-level': 'water-level',
  'munbon-m2m-moisture': 'moisture',
  'munbon-test-devices': 'test'
};

// For production, use a proper queue service
// Options: Upstash Kafka (free tier), Redis Pub/Sub, or direct DB write
const QUEUE_METHOD = process.env.QUEUE_METHOD || 'direct'; // 'direct', 'upstash', 'redis'

export default async function handler(
  req: VercelRequest,
  res: VercelResponse
) {
  // Only accept POST
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  // Validate token from URL
  const { token } = req.query;
  if (!token || typeof token !== 'string' || !VALID_TOKENS[token]) {
    return res.status(401).json({ error: 'Invalid token' });
  }

  const sensorType = VALID_TOKENS[token];
  const timestamp = new Date().toISOString();

  try {
    // Parse request body
    const data = req.body;
    
    // Create message
    const message = {
      messageId: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      token,
      sensorType,
      timestamp,
      data,
      receivedAt: timestamp
    };

    // Route based on configuration
    switch (QUEUE_METHOD) {
      case 'direct':
        // Direct write to database (via API)
        await writeDirectToDatabase(message);
        break;
        
      case 'upstash':
        // Use Upstash Kafka (free tier: 10k messages/day)
        await sendToUpstashKafka(message);
        break;
        
      case 'redis':
        // Use Redis Pub/Sub (via Upstash Redis free tier)
        await sendToRedisQueue(message);
        break;
        
      default:
        // Store in Vercel KV (free tier: 3k requests/day)
        await storeInVercelKV(message);
    }

    // Return success response
    return res.status(200).json({
      message: 'Telemetry data received',
      messageId: message.messageId,
      timestamp
    });

  } catch (error) {
    console.error('Ingestion error:', error);
    return res.status(500).json({ 
      error: 'Failed to process telemetry data' 
    });
  }
}

// Direct database write (recommended for low volume)
async function writeDirectToDatabase(message: any) {
  const response = await fetch(`${process.env.INTERNAL_API_URL}/api/v1/internal/ingest`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Internal-Key': process.env.INTERNAL_API_KEY!
    },
    body: JSON.stringify(message)
  });

  if (!response.ok) {
    throw new Error(`Database write failed: ${response.status}`);
  }
}

// Upstash Kafka (free tier: 10k messages/day)
async function sendToUpstashKafka(message: any) {
  const { Kafka } = await import('@upstash/kafka');
  
  const kafka = new Kafka({
    url: process.env.UPSTASH_KAFKA_REST_URL!,
    username: process.env.UPSTASH_KAFKA_REST_USERNAME!,
    password: process.env.UPSTASH_KAFKA_REST_PASSWORD!,
  });

  const producer = kafka.producer();
  await producer.produce('sensor-data', message);
}

// Redis Queue via Upstash (free tier: 10k commands/day)
async function sendToRedisQueue(message: any) {
  const { Redis } = await import('@upstash/redis');
  
  const redis = new Redis({
    url: process.env.UPSTASH_REDIS_REST_URL!,
    token: process.env.UPSTASH_REDIS_REST_TOKEN!,
  });

  await redis.lpush('sensor-queue', JSON.stringify(message));
}

// Vercel KV Storage (free tier: 3k requests/day)
async function storeInVercelKV(message: any) {
  const { kv } = await import('@vercel/kv');
  
  // Store with TTL of 1 hour (for processing)
  const key = `sensor:${message.messageId}`;
  await kv.set(key, message, { ex: 3600 });
  
  // Add to processing queue
  await kv.lpush('sensor-queue', key);
}