# Complete Deployment Example: Auth Service

This example shows the EXACT steps to deploy the auth service from your local machine to EC2.

## 📂 Current Situation

You have:
- Local code in `/Users/subhajlimanond/dev/munbon2-backend/`
- EC2 instance at `43.209.22.250` with K3s installed
- GitHub repo at `https://github.com/SubhajL/munbon2-backend`

## 🔨 Step 1: Create Auth Service Locally

### 1.1 Create Service Structure
```bash
cd /Users/subhajlimanond/dev/munbon2-backend

# Create directories
mkdir -p services/auth-service/src
mkdir -p services/auth-service/config
mkdir -p services/auth-service/middleware
```

### 1.2 Create the Service Code
```bash
# Main application file
cat > services/auth-service/src/index.js << 'EOF'
const express = require('express');
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const { Pool } = require('pg');

const app = express();
app.use(express.json());

// Database connection
const pool = new Pool({
  host: process.env.POSTGRES_HOST || 'localhost',
  user: process.env.POSTGRES_USER || 'munbon_user',
  password: process.env.POSTGRES_PASSWORD || 'munbon_secure_password',
  database: process.env.POSTGRES_DB || 'munbon_db',
  port: 5432,
});

// Health check endpoint
app.get('/health', (req, res) => {
  res.json({ 
    status: 'healthy', 
    service: 'auth-service',
    version: '1.0.0',
    timestamp: new Date().toISOString()
  });
});

// Login endpoint
app.post('/api/auth/login', async (req, res) => {
  const { email, password } = req.body;
  
  try {
    // Here you would check against database
    // This is a simplified example
    if (email === 'admin@munbon.th' && password === 'admin123') {
      const token = jwt.sign(
        { id: 1, email, role: 'admin' },
        process.env.JWT_SECRET || 'munbon_jwt_secret',
        { expiresIn: '24h' }
      );
      
      res.json({
        success: true,
        token,
        user: { id: 1, email, role: 'admin' }
      });
    } else {
      res.status(401).json({
        success: false,
        message: 'Invalid credentials'
      });
    }
  } catch (error) {
    console.error('Login error:', error);
    res.status(500).json({
      success: false,
      message: 'Internal server error'
    });
  }
});

// Start server
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Auth service running on port ${PORT}`);
});
EOF
```

### 1.3 Create package.json
```bash
cat > services/auth-service/package.json << 'EOF'
{
  "name": "munbon-auth-service",
  "version": "1.0.0",
  "description": "Authentication service for Munbon irrigation system",
  "main": "src/index.js",
  "scripts": {
    "start": "node src/index.js",
    "dev": "nodemon src/index.js"
  },
  "dependencies": {
    "express": "^4.18.2",
    "jsonwebtoken": "^9.0.2",
    "bcryptjs": "^2.4.3",
    "pg": "^8.11.3",
    "dotenv": "^16.3.1"
  },
  "devDependencies": {
    "nodemon": "^3.0.1"
  }
}
EOF
```

### 1.4 Create Dockerfile
```bash
cat > services/auth-service/Dockerfile << 'EOF'
FROM node:18-alpine

# Create app directory
WORKDIR /usr/src/app

# Install dependencies
COPY package*.json ./
RUN npm ci --only=production

# Copy app source
COPY . .

# Expose port
EXPOSE 3000

# Run the application
CMD ["node", "src/index.js"]
EOF
```

### 1.5 Create .dockerignore
```bash
cat > services/auth-service/.dockerignore << 'EOF'
node_modules
npm-debug.log
.env
.git
.gitignore
README.md
.DS_Store
.vscode
.idea
EOF
```

## 🚀 Step 2: Test Locally (Optional)

```bash
cd services/auth-service

# Install dependencies
npm install

# Run locally
npm start

# Test in another terminal
curl http://localhost:3000/health
curl -X POST http://localhost:3000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@munbon.th","password":"admin123"}'
```

## 📤 Step 3: Deploy Using GitHub Actions (Automatic)

### 3.1 Ensure GitHub Secrets are Set
Go to: https://github.com/SubhajL/munbon2-backend/settings/secrets/actions

Required secrets:
- `DOCKER_USERNAME`: subhajl (or your Docker Hub username)
- `DOCKER_PASSWORD`: Your Docker Hub password
- `KUBE_CONFIG_BASE64`: Your K3s kubeconfig in base64

```bash
# If you haven't set KUBE_CONFIG_BASE64 yet:
cat k3s-kubeconfig.yaml | base64 | pbcopy
# Then paste in GitHub secrets
```

### 3.2 Commit and Push Your Code
```bash
# Go back to project root
cd /Users/subhajlimanond/dev/munbon2-backend

# Add all files
git add services/auth-service/

# Commit
git commit -m "feat: add authentication service with JWT support"

# Push to trigger deployment
git push origin main
```

### 3.3 Monitor GitHub Actions
1. Go to: https://github.com/SubhajL/munbon2-backend/actions
2. You'll see your workflow running
3. Click on it to see detailed logs

The workflow will:
- Build Docker image
- Push to Docker Hub as `subhajl/auth-service:latest`
- Deploy to K3s cluster

## 🎯 Step 4: Verify Deployment

### 4.1 Check from Local Machine
```bash
# Set kubeconfig
export KUBECONFIG=/Users/subhajlimanond/dev/munbon2-backend/k3s-kubeconfig.yaml

# Check deployment
kubectl get deployment auth-service -n munbon

# Check pods
kubectl get pods -l app=auth-service -n munbon

# Check logs
kubectl logs -l app=auth-service -n munbon
```

### 4.2 Test the Service
```bash
# Port forward to test locally
kubectl port-forward svc/auth-service 3000:80 -n munbon

# In another terminal, test endpoints
curl http://localhost:3000/health

curl -X POST http://localhost:3000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@munbon.th","password":"admin123"}'
```

## 🔧 Step 5: Manual Deployment (Alternative)

If GitHub Actions isn't working, deploy manually:

### 5.1 Build and Push Docker Image
```bash
cd services/auth-service

# Build image
docker build -t subhajl/auth-service:manual-v1 .

# Push to Docker Hub
docker login
docker push subhajl/auth-service:manual-v1
```

### 5.2 Deploy to K3s
```bash
# Update the image in auth-service.yaml
sed -i '' 's|image: munbon/auth-service:latest|image: subhajl/auth-service:manual-v1|' \
  /Users/subhajlimanond/dev/munbon2-backend/k8s/services/auth-service.yaml

# Apply to cluster
kubectl apply -f /Users/subhajlimanond/dev/munbon2-backend/k8s/services/auth-service.yaml

# Or just update the image
kubectl set image deployment/auth-service \
  auth-service=subhajl/auth-service:manual-v1 -n munbon
```

## 📊 What Happens on EC2/K3s

When you deploy, this happens on the EC2 instance:

1. **K3s receives deployment update**
   ```
   New image: subhajl/auth-service:abc123
   ```

2. **K3s pulls image from Docker Hub**
   ```
   Pulling image "subhajl/auth-service:abc123"
   Successfully pulled image
   ```

3. **Rolling update starts**
   ```
   Creating new pod: auth-service-5d4f5c6d7b-x2n4m
   Waiting for readiness probe...
   New pod ready
   Terminating old pod: auth-service-5d4f5c6d7b-k8s9p
   ```

4. **Service routes to new pods**
   ```
   Service "auth-service" now points to new pods
   Deployment complete
   ```

## 🔍 Troubleshooting

### Image Pull Errors
```bash
# Check if image exists
docker pull subhajl/auth-service:latest

# Check pod events
kubectl describe pod <pod-name> -n munbon
```

### Pod Crash Loop
```bash
# Check logs
kubectl logs <pod-name> -n munbon --previous

# Common issues:
# - Missing environment variables
# - Can't connect to database
# - Port already in use
```

### Can't Access Service
```bash
# Check service endpoints
kubectl get endpoints auth-service -n munbon

# Should show IP addresses
# If empty, pods aren't ready
```

## 📝 Summary

1. **Write code** in `services/auth-service/`
2. **Git push** triggers GitHub Actions
3. **Docker image** built and pushed automatically
4. **K3s pulls** new image and updates pods
5. **Service available** with zero downtime

Total time: ~3-5 minutes from push to running!

## 🎉 Success Checklist

- [ ] Code committed to GitHub
- [ ] GitHub Actions workflow green ✅
- [ ] Docker image in Docker Hub
- [ ] Pods running in K3s
- [ ] Health endpoint responding
- [ ] Login endpoint working

Your auth service is now running on EC2 at 43.209.22.250!