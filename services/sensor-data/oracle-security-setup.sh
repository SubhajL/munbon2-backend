#!/bin/bash

echo "Oracle Cloud Security Setup for AWS Integration"
echo "=============================================="

# 1. Oracle Cloud Firewall Rules
cat > oracle-ingress-rules.sh << 'EOF'
# Allow HTTPS/HTTP from anywhere (for API access)
sudo iptables -A INPUT -p tcp --dport 3000 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 443 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 80 -j ACCEPT

# Save rules
sudo netfilter-persistent save

# Oracle Cloud Security List (via OCI Console)
# Add Ingress Rules:
# - TCP port 3000 from 0.0.0.0/0 (or restrict to AWS Lambda IPs)
# - TCP port 443 from 0.0.0.0/0 (if using HTTPS)
EOF

# 2. SSL Certificate Setup (Optional but Recommended)
cat > setup-ssl.sh << 'EOF'
# Install Certbot
sudo apt update
sudo apt install -y certbot python3-certbot-nginx nginx

# Configure Nginx as reverse proxy
sudo cat > /etc/nginx/sites-available/unified-api << 'NGINX'
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
NGINX

# Enable site
sudo ln -s /etc/nginx/sites-available/unified-api /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl restart nginx

# Get SSL certificate
sudo certbot --nginx -d your-domain.com
EOF

# 3. AWS IAM Role for Oracle VM (if needed)
cat > aws-iam-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "sqs:SendMessage",
        "sqs:GetQueueUrl"
      ],
      "Resource": "arn:aws:sqs:ap-southeast-1:*:sensor-data-queue"
    },
    {
      "Effect": "Allow",
      "Action": [
        "lambda:InvokeFunction"
      ],
      "Resource": "arn:aws:lambda:ap-southeast-1:*:function:munbon-*"
    }
  ]
}
EOF

echo "Setup complete! Update Parameter Store:"
echo "aws ssm put-parameter --name '/munbon/oracle-api-endpoint' --value 'http://YOUR_ORACLE_IP:3000' --type 'String' --overwrite"