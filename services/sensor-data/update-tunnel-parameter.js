#!/usr/bin/env node

const { SSMClient, PutParameterCommand } = require('@aws-sdk/client-ssm');
const { execSync } = require('child_process');

// Create SSM client
const ssmClient = new SSMClient({ region: 'ap-southeast-1' });

// Get current tunnel URL from PM2 logs
const getTunnelUrl = () => {
  try {
    const logs = execSync('pm2 logs quick-tunnel --lines 50 --nostream', { encoding: 'utf8' });
    const match = logs.match(/https:\/\/[a-z-]+\.trycloudflare\.com/g);
    if (match) {
      return match[match.length - 1];
    }
  } catch (err) {
    console.error('Error getting tunnel URL from PM2:', err.message);
  }
  return null;
};

// Update Parameter Store
const updateParameter = async (tunnelUrl) => {
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
  } catch (error) {
    console.error('❌ Error updating Parameter Store:', error.message);
    console.log('\nMake sure you have AWS credentials configured:');
    console.log('  aws configure');
  }
};

// Main execution
async function main() {
  console.log('🔄 Updating Tunnel URL in AWS Parameter Store');
  console.log('===========================================');
  
  const tunnelUrl = getTunnelUrl();
  
  if (!tunnelUrl) {
    console.error('❌ No tunnel URL found. Make sure quick-tunnel is running.');
    process.exit(1);
  }
  
  console.log('📡 Current tunnel URL:', tunnelUrl);
  await updateParameter(tunnelUrl);
  
  console.log('\n✨ Lambda functions will automatically use the new URL!');
  console.log('   (No redeployment needed - reads dynamically)');
}

main().catch(console.error);