# EC2 Connection Debug Guide

## The "Connection refused" error means one of these:

1. **EC2 instance is stopped**
   - Check AWS Console → EC2 → Instances
   - Make sure your instance is in "Running" state

2. **Security Group doesn't allow SSH (port 22)**
   - Go to EC2 instance → Security → Security groups
   - Check Inbound rules
   - Must have: SSH (22) from your IP or 0.0.0.0/0

3. **Wrong EC2_HOST value**
   - Should be public IP or public DNS of EC2
   - Format: `54.123.45.67` or `ec2-54-123-45-67.region.compute.amazonaws.com`

4. **EC2 instance firewall blocking SSH**
   - Sometimes Ubuntu firewall (ufw) blocks connections

## Quick Checks:

### 1. Check if EC2 is running:
```bash
# In AWS Console
EC2 → Instances → Check Status
```

### 2. Check Security Group:
```bash
# In AWS Console
EC2 → Instances → [Your Instance] → Security → Security groups → Inbound rules
# Should have:
Type: SSH
Protocol: TCP
Port: 22
Source: 0.0.0.0/0 (or your IP)
```

### 3. Check EC2_HOST in GitHub Secrets:
- Go to: https://github.com/SubhajL/munbon2-backend/settings/secrets/actions
- Click on EC2_HOST
- Update with correct public IP

### 4. Test from your local machine:
```bash
# Replace with your values
ssh -i your-key.pem ubuntu@your-ec2-ip
```

## Alternative: Use GitHub-hosted runner IP
If your EC2 security group is too restrictive, you might need to:
1. Allow GitHub Actions IP ranges
2. Or temporarily allow 0.0.0.0/0 for SSH during deployment