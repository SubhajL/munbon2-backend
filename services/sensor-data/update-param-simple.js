#!/usr/bin/env node

const { SSMClient, PutParameterCommand } = require('@aws-sdk/client-ssm');
const fs = require('fs');

// Create SSM client
const ssmClient = new SSMClient({ region: 'ap-southeast-1' });

// Read tunnel URL from file
const tunnelUrl = fs.readFileSync('tunnel-url.txt', 'utf8').trim();

console.log('🔄 Updating AWS Parameter Store');
console.log('================================');
console.log('Tunnel URL:', tunnelUrl);

// Update Parameter Store
async function updateParameter() {
  try {
    const command = new PutParameterCommand({
      Name: '/munbon/tunnel-url',
      Value: tunnelUrl,
      Type: 'String',
      Overwrite: true,
      Description: 'Cloudflare tunnel URL for Munbon API'
    });
    
    await ssmClient.send(command);
    console.log('✅ Updated Parameter Store successfully!');
    console.log('   Parameter: /munbon/tunnel-url');
    console.log('   Value:', tunnelUrl);
    console.log('\n✨ Lambda functions will automatically use the new URL!');
  } catch (error) {
    console.error('❌ Error updating Parameter Store:', error.message);
    console.log('\nMake sure you have AWS credentials configured:');
    console.log('  export AWS_ACCESS_KEY_ID=your_key');
    console.log('  export AWS_SECRET_ACCESS_KEY=your_secret');
    console.log('  export AWS_REGION=ap-southeast-1');
  }
}

updateParameter();