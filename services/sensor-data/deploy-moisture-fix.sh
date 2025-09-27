#!/bin/bash

echo "🔧 Deploying moisture data processor fix to EC2..."

# SSH connection details
EC2_HOST="43.208.201.191"
EC2_USER="ubuntu"
SSH_KEY="$HOME/dev/th-lab01.pem"

# First, backup the current file
echo "📦 Backing up current simple-http-server.js..."
ssh -i $SSH_KEY $EC2_USER@$EC2_HOST "cp /home/ubuntu/munbon2-backend/services/sensor-data/src/simple-http-server.js /home/ubuntu/munbon2-backend/services/sensor-data/src/simple-http-server.js.backup-$(date +%Y%m%d-%H%M%S)"

# Create the fixed version
echo "✏️ Creating fixed version..."
ssh -i $SSH_KEY $EC2_USER@$EC2_HOST 'cat > /tmp/fix-moisture-processor.patch << "EOF"
--- a/simple-http-server.js
+++ b/simple-http-server.js
@@ -54,7 +54,17 @@
     // Insert data directly to database using correct column names
     for (const sensor of sensors) {
       const query = `
         INSERT INTO moisture_readings (
           time,
           sensor_id,
           location_lat,
           location_lng,
           moisture_surface_pct,
+          moisture_deep_pct,
           temp_surface_c,
-          voltage
-        ) VALUES ($1, $2, $3, $4, $5, $6, $7)
+          temp_deep_c,
+          ambient_humidity_pct,
+          ambient_temp_c,
+          voltage,
+          flood_status,
+          quality_score
+        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
       `;
       
       await dbPool.query(query, [
         timestamp,
-        sensor.sensor_id || gatewayId,
+        gatewayId.padStart(4, "0") + "-" + (sensor.sensor_id || "").padStart(4, "0"),
         lat,
         lng,
-        sensor.moisture || null,
-        sensor.temperature || null,
-        sensor.battery || null
+        parseFloat(sensor.humid_hi) || null,
+        parseFloat(sensor.humid_low) || null,
+        parseFloat(sensor.temp_hi) || null,
+        parseFloat(sensor.temp_low) || null,
+        parseFloat(sensor.amb_humid) || null,
+        parseFloat(sensor.amb_temp) || null,
+        sensor.sensor_batt ? parseFloat(sensor.sensor_batt) / 100 : null,
+        sensor.flood === "yes",
+        0.95
       ]);
     }
EOF'

# Apply the fix
echo "🚀 Applying the fix..."
ssh -i $SSH_KEY $EC2_USER@$EC2_HOST "cd /home/ubuntu/munbon2-backend/services/sensor-data/src && patch -p1 < /tmp/fix-moisture-processor.patch"

# Restart the service
echo "🔄 Restarting moisture-http service..."
ssh -i $SSH_KEY $EC2_USER@$EC2_HOST "pm2 restart moisture-http"

# Check service status
echo "✅ Checking service status..."
ssh -i $SSH_KEY $EC2_USER@$EC2_HOST "pm2 status moisture-http"

echo "✨ Fix deployed successfully!"