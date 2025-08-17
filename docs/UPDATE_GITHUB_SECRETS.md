# Update GitHub Secrets for EC2 Deployment

Your EC2 instance is running! Here's what you need to update:

## 1. Update GitHub Secrets

Go to: https://github.com/SubhajL/munbon2-backend/settings/secrets/actions

Update these secrets:
- **EC2_HOST**: `43.209.22.250`
- **EC2_USER**: `ubuntu`
- **EC2_SSH_KEY**: (Copy the contents of your th-lab01.pem file)

## 2. How to copy your SSH key:

```bash
# On your Mac, run:
cat ~/path/to/th-lab01.pem
```

Copy the entire output (including the BEGIN and END lines) and paste it as the EC2_SSH_KEY secret.

## 3. Verify EC2 Setup

Your EC2 details:
- Public IP: 43.209.22.250
- Username: ubuntu
- OS: Ubuntu 24.04.2 LTS
- Instance appears to be in AWS Asia Pacific region

## 4. Check if Docker is installed on EC2:

```bash
# SSH into your EC2
ssh -i th-lab01.pem ubuntu@43.209.22.250

# Check Docker
docker --version
docker compose version

# If not installed, the GitHub Actions will install it automatically
```

## 5. Security Group Check

Make sure your EC2 security group allows:
- SSH (port 22) - Already working ✓
- HTTP (ports 3001-3014) - For accessing services
- HTTPS (port 443) - Optional

## Next Steps:
1. Update the GitHub secrets with correct values
2. The deployment should work once secrets are updated
3. The workflow will automatically install Docker if needed