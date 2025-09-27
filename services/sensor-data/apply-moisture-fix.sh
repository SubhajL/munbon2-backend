#!/bin/bash

echo "🔧 Fixing moisture data processor on EC2..."

# SSH connection details
EC2_HOST="43.208.201.191"
EC2_USER="ubuntu"
SSH_KEY="$HOME/dev/th-lab01.pem"

# Backup current file
echo "📦 Backing up current file..."
ssh -i $SSH_KEY $EC2_USER@$EC2_HOST "cp /home/ubuntu/munbon2-backend/services/sensor-data/src/simple-http-server.js /home/ubuntu/munbon2-backend/services/sensor-data/src/simple-http-server.js.backup-$(date +%Y%m%d-%H%M%S)"

# Update the moisture processing section
echo "✏️ Updating moisture processor..."
ssh -i $SSH_KEY $EC2_USER@$EC2_HOST "sed -i.bak '
/INSERT INTO moisture_readings/,/\]);$/{
  s/moisture_surface_pct,/moisture_surface_pct,\
          moisture_deep_pct,/
  s/temp_surface_c,/temp_surface_c,\
          temp_deep_c,\
          ambient_humidity_pct,\
          ambient_temp_c,/
  s/) VALUES (\$1, \$2, \$3, \$4, \$5, \$6, \$7)/) VALUES (\$1, \$2, \$3, \$4, \$5, \$6, \$7, \$8, \$9, \$10, \$11, \$12, \$13)/
  s/sensor\.sensor_id || gatewayId,/gatewayId.padStart(4, \"0\") + \"-\" + (sensor.sensor_id || \"\").padStart(4, \"0\"),/
  s/sensor\.moisture || null,/parseFloat(sensor.humid_hi) || null,\
        parseFloat(sensor.humid_low) || null,/
  s/sensor\.temperature || null,/parseFloat(sensor.temp_hi) || null,\
        parseFloat(sensor.temp_low) || null,\
        parseFloat(sensor.amb_humid) || null,\
        parseFloat(sensor.amb_temp) || null,/
  s/sensor\.battery || null/sensor.sensor_batt ? parseFloat(sensor.sensor_batt) \/ 100 : null,\
        sensor.flood === \"yes\",\
        0.95/
}' /home/ubuntu/munbon2-backend/services/sensor-data/src/simple-http-server.js"

# Restart the service
echo "🔄 Restarting moisture-http service..."
ssh -i $SSH_KEY $EC2_USER@$EC2_HOST "pm2 restart moisture-http"

# Check service status
echo "✅ Checking service status..."
ssh -i $SSH_KEY $EC2_USER@$EC2_HOST "pm2 list | grep moisture-http"

echo "✨ Fix deployed!"
echo ""
echo "Test with:"
echo "curl -X POST http://$EC2_HOST:8080/api/sensor-data/moisture/munbon-m2m-moisture \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d @test-moisture-payload.json"