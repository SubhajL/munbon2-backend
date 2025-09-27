#!/bin/bash

echo "Deploying updated consumer with sensor ID mapping to EC2..."

# Copy updated files to EC2
echo "Copying dist files..."
scp -i ~/dev/th-lab01.pem -r services/sensor-data/dist/* ubuntu@43.208.201.191:/home/ubuntu/munbon2-backend/services/sensor-data/dist/

# Restart consumer on EC2
echo "Restarting consumer..."
ssh -i ~/dev/th-lab01.pem ubuntu@43.208.201.191 "pm2 restart sqs-consumer"

echo "Deployment complete!"

# Check status
echo ""
echo "Checking consumer status..."
ssh -i ~/dev/th-lab01.pem ubuntu@43.208.201.191 "pm2 list | grep sqs-consumer"