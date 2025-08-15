# GitHub Secrets Setup for EC2 Deployment

## ⚠️ SECURITY NOTICE
The SSH private key that was previously in this file has been REMOVED for security reasons.
NEVER commit SSH private keys or any secrets to version control.

## Required GitHub Secrets

Add these secrets to your GitHub repository:

1. Go to: https://github.com/SubhajL/munbon2-backend
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret** for each:

### Secret 1: EC2_HOST
```
43.209.22.250
```

### Secret 2: EC2_USER
```
ubuntu
```

### Secret 3: EC2_SSH_KEY
```
[REDACTED - Add your private key here directly in GitHub Secrets]
```

## Security Best Practices

1. **Generate a new SSH key pair** since the previous one was exposed
2. **Update the EC2 instance** with the new public key
3. **Use AWS Systems Manager** Session Manager for keyless access (recommended)
4. **Never commit secrets** to the repository

## Alternative: AWS Systems Manager (Recommended)

Instead of SSH keys, use AWS IAM roles and Systems Manager:

1. Attach IAM role to EC2 instance with SSM permissions
2. Use GitHub OIDC provider for authentication
3. Access EC2 via Session Manager (no SSH keys needed)

## After Adding Secrets

1. Any push to `main` branch will automatically deploy to EC2
2. You can manually trigger deployment from Actions tab
3. Monitor deployment logs in GitHub Actions

## Testing Deployment

For local testing (with proper SSH key):
```bash
# DO NOT include the actual key path in documentation
./scripts/deploy-to-ec2.sh <EC2_IP> <PATH_TO_PRIVATE_KEY>
```