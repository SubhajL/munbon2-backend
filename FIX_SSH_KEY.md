# How to Fix SSH Key Issue

## The Problem
GitHub Secrets mangles multi-line SSH keys. Your base64-encoded key isn't being decoded properly.

## Immediate Solution

### Option 1: Re-add the key as plain text with proper newlines
1. On your Mac, view your key:
   ```bash
   cat th-lab01.pem
   ```

2. Copy the ENTIRE output including:
   - `-----BEGIN RSA PRIVATE KEY-----`
   - All the key content
   - `-----END RSA PRIVATE KEY-----`

3. Go to GitHub Settings → Secrets → EC2_SSH_KEY → Update

4. Paste the key EXACTLY as shown

5. Run "Deploy Simple SSH" workflow (uses proven SSH action)

### Option 2: Keep base64 but fix the decode
The issue is that your base64 string needs proper decoding. The workflow "Deploy Simple SSH" uses a battle-tested SSH action that handles keys properly.

## Better Long-term Alternatives

### 1. AWS Systems Manager (Best for EC2)
- No SSH keys needed
- Use AWS IAM roles
- More secure
- Example: `aws ssm send-command`

### 2. GitHub Environments with Deploy Keys
- Use GitHub's deployment environments
- Store keys per environment
- Approval workflows

### 3. AWS CodeDeploy
- Native AWS deployment service
- Integrates with GitHub
- No SSH needed

### 4. Container Services (ECS/EKS)
- Use AWS container services
- GitHub Actions can push directly
- No SSH to EC2 needed

### 5. GitHub OIDC with AWS
- No long-lived credentials
- GitHub assumes AWS role temporarily
- Most secure option

## Why Current Approach is Problematic
1. SSH key management is error-prone
2. Manual docker-compose on EC2 is not scalable
3. No rollback capability
4. No health checks
5. Single point of failure

## Recommended Next Steps
1. Get deployment working with "Deploy Simple SSH" workflow
2. Plan migration to AWS ECS or EKS
3. Implement proper CI/CD with AWS CodePipeline
4. Use infrastructure as code (Terraform/CloudFormation)