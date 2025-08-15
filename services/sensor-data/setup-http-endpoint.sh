#!/bin/bash

echo "Setting up HTTP endpoint for legacy moisture sensors"
echo "===================================================="
echo ""
echo "Option 1: Using ngrok (easiest for testing)"
echo "-------------------------------------------"
echo "1. Install ngrok: brew install ngrok"
echo "2. Start sensor service: npm run dev"
echo "3. In another terminal: ngrok http 3003"
echo "4. Give manufacturer the HTTP URL from ngrok"
echo ""
echo "Option 2: Direct AWS Lambda (bypass CloudFlare)"
echo "-----------------------------------------------"
echo "Since you already have AWS Lambda for water level sensors,"
echo "you could use the same approach for moisture sensors:"
echo "- Create Lambda function that accepts HTTP (API Gateway with HTTP, not HTTPS)"
echo "- Lambda puts data into SQS"
echo "- Your local consumer processes it"
echo ""
echo "Option 3: Separate HTTP-only server"
echo "------------------------------------"
echo "Run a dedicated HTTP server just for legacy devices:"

cat > legacy-http-server.js << 'EOF'
const express = require('express');
const axios = require('axios');

const app = express();
app.use(express.json());

// Simple HTTP proxy to local service
app.post('/api/v1/:token/telemetry', async (req, res) => {
  try {
    // Forward to local service
    const response = await axios.post(
      `http://localhost:3003/api/v1/${req.params.token}/telemetry`,
      req.body,
      { headers: { 'Content-Type': 'application/json' } }
    );
    res.json(response.data);
  } catch (error) {
    console.error('Proxy error:', error.message);
    res.status(error.response?.status || 500).json({
      error: error.response?.data || 'Proxy error'
    });
  }
});

const PORT = 8080; // Different port for HTTP
app.listen(PORT, '0.0.0.0', () => {
  console.log(`Legacy HTTP server running on port ${PORT}`);
  console.log(`Accepting HTTP requests for legacy devices`);
});
EOF

echo ""
echo "To run the HTTP proxy:"
echo "node legacy-http-server.js"
echo ""
echo "Then expose port 8080 via your router or ngrok"