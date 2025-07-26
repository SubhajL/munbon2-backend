# Docker Hub Setup Guide for Munbon Backend

## 1. Create Docker Hub Account (Free Plan)

1. Go to https://hub.docker.com/signup
2. Create a free account with:
   - Username: (e.g., `subhajl` or your preferred username)
   - Email: Your email address
   - Password: Strong password
3. Verify your email

## 2. Create Repositories

After logging in to Docker Hub, create repositories for each service:

### Required Repositories (Click "Create Repository" for each):
- `[username]/munbon-sensor-data`
- `[username]/munbon-auth`
- `[username]/munbon-moisture-monitoring`
- `[username]/munbon-weather-monitoring`
- `[username]/munbon-water-level-monitoring`
- `[username]/munbon-gis`
- `[username]/munbon-rid-ms`
- `[username]/munbon-ros`
- `[username]/munbon-awd-control`
- `[username]/munbon-flow-monitoring`
- `[username]/munbon-gravity-optimizer`
- `[username]/munbon-water-accounting`
- `[username]/munbon-sensor-network-management`

**Note**: Replace `[username]` with your Docker Hub username.

## 3. GitHub Secrets Setup

Add these secrets to your GitHub repository:
1. Go to Settings → Secrets and variables → Actions
2. Add these secrets:
   - `DOCKERHUB_USERNAME`: Your Docker Hub username
   - `DOCKERHUB_TOKEN`: Create an access token from Docker Hub
     - Go to Docker Hub → Account Settings → Security → Access Tokens
     - Click "New Access Token"
     - Description: "GitHub Actions Munbon"
     - Permissions: Read, Write, Delete
     - Copy the generated token
   - **Existing secrets to keep**: EC2_HOST, EC2_USER, EC2_SSH_KEY

## 4. Docker Hub Rate Limits (Free Plan)

- **Anonymous users**: 100 pulls per 6 hours per IP
- **Authenticated users**: 200 pulls per 6 hours
- **Pushes**: Unlimited
- **Storage**: Unlimited public repositories

## 5. How It Works

### Build & Push Phase (GitHub Actions)
1. Developer pushes code to main branch
2. GitHub Actions triggers the workflow
3. Each service is built in parallel on GitHub's servers
4. Built images are tagged with both `latest` and commit SHA
5. Images are pushed to Docker Hub

### Deploy Phase (EC2)
1. GitHub Actions SSHs into EC2
2. Updates the code repository on EC2
3. Pulls the latest images from Docker Hub (no building!)
4. Restarts containers with new images
5. Performs health checks

### Benefits
- **Faster deployments**: Pull pre-built images instead of building on EC2
- **Less EC2 resource usage**: No CPU/memory spent on building
- **Version control**: Each image tagged with commit SHA
- **Rollback capability**: Can revert to previous image versions
- **Central image repository**: Images available from anywhere

## 6. Testing the Setup

After setting up Docker Hub and GitHub secrets:

1. **Test locally** (if you have Docker installed):
   ```bash
   # Export your Docker Hub username
   export DOCKERHUB_USERNAME=your-username
   
   # Pull and run a service
   docker compose -f docker-compose.ec2.yml pull sensor-data
   docker compose -f docker-compose.ec2.yml up sensor-data
   ```

2. **Trigger GitHub Actions**:
   - Make a small change and push to main
   - Watch the Actions tab in GitHub
   - Verify images appear in Docker Hub

3. **Check EC2 deployment**:
   - SSH into EC2 and check containers:
   ```bash
   docker ps
   docker images
   ```

## 7. Troubleshooting

### Common Issues:
1. **"repository does not exist"**: Create the repository on Docker Hub first
2. **"unauthorized"**: Check DOCKERHUB_TOKEN is correctly set in GitHub Secrets
3. **"rate limit exceeded"**: Use authenticated pulls (token in docker login)
4. **"no space left"**: Clean up old images on EC2 with `docker system prune -a`

### Useful Commands on EC2:
```bash
# View running containers
docker ps

# View all images
docker images

# Check logs
docker logs munbon-sensor-data

# Pull latest images manually
DOCKERHUB_USERNAME=your-username docker compose -f docker-compose.ec2.yml pull

# Restart services
docker compose -f docker-compose.ec2.yml restart
```