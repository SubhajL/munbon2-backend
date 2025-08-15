const axios = require('axios');

async function testHealth() {
  try {
    console.log('Testing health endpoint...');
    const response = await axios.get('http://localhost:3003/health');
    console.log('Health response:', response.data);
  } catch (error) {
    console.error('Error:', error.message);
  }
}

testHealth();