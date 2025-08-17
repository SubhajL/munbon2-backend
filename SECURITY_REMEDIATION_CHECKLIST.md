# Security Remediation Checklist

## IMMEDIATE ACTIONS REQUIRED

### 1. AWS Credentials (CRITICAL - Do this FIRST)
- [ ] Log into AWS Console
- [ ] Go to IAM → Users → Your User → Security credentials
- [ ] Delete the exposed Access Key
- [ ] Create new Access Key
- [ ] Update local AWS CLI: `aws configure`
- [ ] Update all services using AWS credentials

### 2. Database Passwords
#### EC2 PostgreSQL (43.209.22.250)
- [ ] SSH into EC2 instance
- [ ] Change postgres password: `sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'new-secure-password';"`
- [ ] Update all services connecting to this database

#### MSSQL (moonup.hopto.org)
- [ ] Connect to MSSQL server
- [ ] Change sa password: `ALTER LOGIN sa WITH PASSWORD = 'new-secure-password';`
- [ ] Update all services using this connection

### 3. SSH Keys
- [ ] Create new EC2 key pair in AWS Console
- [ ] Download new .pem file
- [ ] Update EC2 instance to use new key
- [ ] Delete old key from AWS
- [ ] Update GitHub secrets with new key

### 4. Clean Git History
- [ ] Install git-filter-repo: `brew install git-filter-repo`
- [ ] Run: `./clean-git-history.sh`
- [ ] Force push to GitHub: `git push --force-with-lease origin main`
- [ ] Notify all team members to re-clone the repository

### 5. GitHub Security
- [ ] Go to GitHub repo → Settings → Secrets and variables → Actions
- [ ] Update all secrets with new values
- [ ] Enable secret scanning: Settings → Security → Code security
- [ ] Review secret scanning alerts

### 6. Update Services
- [ ] Create new .env files for each service using .env.example
- [ ] Deploy updated services with new credentials
- [ ] Verify all services are working with new credentials

### 7. Monitoring
- [ ] Check AWS CloudTrail for any unauthorized access
- [ ] Review database logs for suspicious activity
- [ ] Monitor services for next 24-48 hours

## Prevention Measures
1. Never commit .env files
2. Use AWS IAM roles instead of keys when possible
3. Use GitHub Secrets for CI/CD
4. Regular credential rotation
5. Use tools like git-secrets to prevent commits

## Emergency Contacts
- AWS Support: [Your support plan]
- Database Admin: [Contact info]
- Security Team: [Contact info]