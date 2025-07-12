// Lambda function calling Oracle-hosted Unified API

const axios = require('axios');
const { SSMClient, GetParameterCommand } = require('@aws-sdk/client-ssm');

const ssmClient = new SSMClient({ region: 'ap-southeast-1' });

// Get Oracle VM endpoint from Parameter Store
async function getOracleEndpoint() {
  try {
    const command = new GetParameterCommand({
      Name: '/munbon/oracle-api-endpoint',
      WithDecryption: false
    });
    
    const response = await ssmClient.send(command);
    return response.Parameter.Value; // e.g., "http://132.226.xxx.xxx:3000"
  } catch (error) {
    console.error('Error getting endpoint:', error);
    // Fallback to environment variable
    return process.env.ORACLE_API_ENDPOINT;
  }
}

exports.handler = async (event) => {
  try {
    // Get the Oracle endpoint
    const apiEndpoint = await getOracleEndpoint();
    
    // Parse request
    const { resource, httpMethod, queryStringParameters, headers, body } = event;
    
    // Forward request to Oracle Unified API
    const response = await axios({
      method: httpMethod,
      url: `${apiEndpoint}${resource}`,
      params: queryStringParameters,
      headers: {
        'X-Internal-Key': process.env.INTERNAL_API_KEY,
        ...headers
      },
      data: body ? JSON.parse(body) : undefined,
      timeout: 29000 // Lambda timeout is 30s
    });
    
    return {
      statusCode: 200,
      headers: {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*'
      },
      body: JSON.stringify(response.data)
    };
    
  } catch (error) {
    console.error('Error:', error);
    
    return {
      statusCode: error.response?.status || 500,
      body: JSON.stringify({
        error: error.message,
        details: 'Could not reach Oracle unified API'
      })
    };
  }
};