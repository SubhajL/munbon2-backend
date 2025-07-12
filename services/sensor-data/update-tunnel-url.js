#!/usr/bin/env node

const fs = require('fs');
const { exec } = require('child_process');
const path = require('path');

// Read tunnel log to get URL
const getTunnelUrl = () => {
  try {
    const log = fs.readFileSync('tunnel.log', 'utf8');
    const match = log.match(/https:\/\/[a-z-]+\.trycloudflare\.com/g);
    if (match) {
      // Get the last (most recent) URL
      return match[match.length - 1];
    }
  } catch (err) {
    console.error('Error reading tunnel log:', err);
  }
  return null;
};

// Update serverless config
const updateServerlessConfig = (tunnelUrl) => {
  const configPath = path.join(__dirname, 'deployments/aws-lambda/serverless-data-api.yml');
  let config = fs.readFileSync(configPath, 'utf8');
  
  // Update the default tunnel URL
  config = config.replace(
    /TUNNEL_URL: \${env:TUNNEL_URL, '[^']+'/,
    `TUNNEL_URL: \${env:TUNNEL_URL, '${tunnelUrl}'`
  );
  
  fs.writeFileSync(configPath, config);
  console.log('Updated serverless config with new tunnel URL');
};

// Deploy to Lambda
const deployToLambda = () => {
  console.log('Deploying to Lambda...');
  const deployCmd = 'cd deployments/aws-lambda && TUNNEL_URL=' + tunnelUrl + ' npx serverless deploy --config serverless-data-api.yml --stage prod --region ap-southeast-1';
  
  exec(deployCmd, (error, stdout, stderr) => {
    if (error) {
      console.error('Deployment error:', error);
      return;
    }
    console.log('Lambda deployment complete!');
    console.log('Test with:');
    console.log('curl -H "X-API-Key: rid-ms-prod-key1" https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/water-levels/latest');
  });
};

// Main execution
console.log('Checking for tunnel URL...');
const tunnelUrl = getTunnelUrl();

if (tunnelUrl) {
  console.log('Found tunnel URL:', tunnelUrl);
  updateServerlessConfig(tunnelUrl);
  
  // Optional: Auto-deploy (uncomment if you want automatic deployment)
  // deployToLambda();
  
  // Or just show the command to run
  console.log('\nTo deploy, run:');
  console.log(`cd deployments/aws-lambda && TUNNEL_URL=${tunnelUrl} npx serverless deploy --config serverless-data-api.yml --stage prod`);
} else {
  console.log('No tunnel URL found yet. Waiting...');
  setTimeout(() => {
    process.exit(0);
  }, 5000);
}