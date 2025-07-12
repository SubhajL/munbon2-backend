const axios = require('axios');

const TUNNEL_URL = 'https://munbon-api-proxy.beautifyai.io';
const INTERNAL_API_KEY = 'munbon-internal-f3b89263126548';

async function testProxy() {
  console.log('Testing local proxy connection...\n');
  
  try {
    // Test health endpoint
    console.log('1. Testing health endpoint:');
    const healthResponse = await axios.get(`${TUNNEL_URL}/health`, {
      headers: {
        'X-Internal-Key': INTERNAL_API_KEY,
      },
    });
    console.log('✓ Health:', healthResponse.data);
    
    // Test water level latest
    console.log('\n2. Testing water level latest:');
    const waterResponse = await axios.get(`${TUNNEL_URL}/api/v1/sensors/water-level/latest`, {
      headers: {
        'X-Internal-Key': INTERNAL_API_KEY,
      },
    });
    console.log('✓ Water Level Response:', JSON.stringify(waterResponse.data, null, 2));
    
  } catch (error) {
    console.error('Error:', error.message);
    if (error.response) {
      console.error('Response data:', error.response.data);
      console.error('Response status:', error.response.status);
    }
  }
}

testProxy();