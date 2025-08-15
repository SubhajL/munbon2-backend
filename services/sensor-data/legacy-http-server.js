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
