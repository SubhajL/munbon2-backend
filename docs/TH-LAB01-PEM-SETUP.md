# Using th-lab01.pem for GitHub Secrets

## Quick Setup Commands

### If you have GitHub CLI installed:
```bash
# Navigate to your project
cd /Users/subhajlimanond/dev/munbon2-backend

# Set the secrets using your PEM file
gh secret set EC2_HOST -R SubhajL/munbon2-backend -b "43.209.22.250"
gh secret set EC2_USER -R SubhajL/munbon2-backend -b "ubuntu"
gh secret set EC2_SSH_KEY -R SubhajL/munbon2-backend < /path/to/th-lab01.pem
```

### Manual Setup:
1. Copy your PEM file contents:
   ```bash
   cat th-lab01.pem
   ```

2. Go to: https://github.com/SubhajL/munbon2-backend/settings/secrets/actions

3. Add three secrets:
   - **EC2_HOST**: `43.209.22.250`
   - **EC2_USER**: `ubuntu`
   - **EC2_SSH_KEY**: (paste entire th-lab01.pem contents)

## Verify Your PEM File

Make sure th-lab01.pem has the correct format:
```bash
# Check the first line
head -1 th-lab01.pem
```

Should show either:
- `-----BEGIN RSA PRIVATE KEY-----` (RSA format - OK)
- `-----BEGIN OPENSSH PRIVATE KEY-----` (OpenSSH format - OK)

## Test SSH Connection First

Before setting up GitHub secrets, verify the PEM works:
```bash
ssh -i th-lab01.pem ubuntu@43.209.22.250
```

If this works, then the PEM file is correct and can be used for GitHub Actions.