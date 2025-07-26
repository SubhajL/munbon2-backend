# Docker Hub Repository Creation Guide

## Correct Repository Naming Format

When creating repositories on Docker Hub, follow these rules:

### 1. Repository Name Format
- **Format**: `username/repository-name`
- **Example**: If your username is `subhajl`, create: `subhajl/munbon-sensor-data`

### 2. Creating Repositories - Step by Step

1. **Login to Docker Hub**
2. **Click "Create Repository"**
3. **Fill in the form**:
   - **Namespace**: This should be auto-filled with your username
   - **Repository Name**: Enter just the service name (e.g., `munbon-sensor-data`)
   - **Description**: (Optional) "Munbon Sensor Data Service"
   - **Visibility**: Public (for free plan)

### 3. Repository Names to Create

Create these repositories (just enter the part after the slash):
- `munbon-sensor-data`
- `munbon-auth`
- `munbon-moisture-monitoring`
- `munbon-weather-monitoring`
- `munbon-water-level-monitoring`
- `munbon-gis`
- `munbon-rid-ms`
- `munbon-ros`
- `munbon-awd-control`
- `munbon-flow-monitoring`
- `munbon-gravity-optimizer`
- `munbon-water-accounting`
- `munbon-sensor-network-management`

### 4. Common Issues

1. **"Invalid repository name"**:
   - Don't include your username in the repository name field
   - Use only lowercase letters, numbers, and hyphens
   - Don't use underscores

2. **"Repository already exists"**:
   - You or someone else already created it
   - Try a different name or check your existing repositories

### 5. Alternative: Create via Docker CLI

If the web interface gives issues, you can create by pushing:
```bash
# Login first
docker login

# Tag a dummy image
docker pull hello-world
docker tag hello-world:latest yourusername/munbon-sensor-data:latest

# Push (this creates the repository)
docker push yourusername/munbon-sensor-data:latest
```

### 6. What the Form Should Look Like

```
Namespace: [subhajl] (auto-filled)
Repository Name: munbon-sensor-data
Short Description: Munbon Sensor Data Service
Visibility: ( ) Private (X) Public
```

Don't put "subhajl/munbon-sensor-data" in the repository name field - just "munbon-sensor-data".