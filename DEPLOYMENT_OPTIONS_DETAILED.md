# Detailed Deployment Options Analysis

## Current Setup Issues
- Manual SSH key management (error-prone)
- No auto-scaling
- No health checks or auto-recovery
- Manual docker-compose on single EC2
- No rollback capability

## Option 1: AWS ECS with Fargate

### Overview
Amazon ECS (Elastic Container Service) with Fargate is a serverless container platform. You don't manage servers - just define your containers and AWS runs them.

### Architecture
```
GitHub Actions → Build Docker → Push to ECR → ECS Service Update → Fargate runs containers
```

### Implementation Steps
1. Create ECR (Elastic Container Registry) repositories
2. Create ECS Cluster
3. Define Task Definitions (like docker-compose but for ECS)
4. Create ECS Services with ALB (Application Load Balancer)
5. GitHub Actions workflow pushes to ECR and updates ECS

### Cost Breakdown (Monthly Estimate)
```
Fargate (3 services × 0.5 vCPU × 1GB RAM each):
- vCPU: 3 × 0.5 × $0.04048/hour × 730 hours = $44.33
- Memory: 3 × 1GB × $0.004445/hour × 730 hours = $9.73
- ALB: ~$20/month
- ECR Storage: ~$10/month (for container images)
- NAT Gateway (if private subnets): $45/month

Total: ~$130-175/month
```

### Pros
- No server management
- Auto-scaling built-in
- Health checks and auto-recovery
- Blue/green deployments
- Integrated with AWS services

### Cons
- More expensive than single EC2
- Learning curve for ECS
- Requires VPC/networking setup

### Example GitHub Actions Workflow
```yaml
- name: Deploy to ECS
  run: |
    aws ecr get-login-password | docker login --username AWS --password-stdin $ECR_REGISTRY
    docker build -t $ECR_REGISTRY/$ECR_REPOSITORY:latest .
    docker push $ECR_REGISTRY/$ECR_REPOSITORY:latest
    aws ecs update-service --cluster my-cluster --service my-service --force-new-deployment
```

---

## Option 2: GitHub OIDC + AWS (Secure Credential Management)

### Overview
OpenID Connect (OIDC) allows GitHub Actions to authenticate with AWS without storing long-lived credentials. GitHub generates temporary tokens for each workflow run.

### Architecture
```
GitHub Actions → Request OIDC token → Assume AWS IAM Role → Deploy to any AWS service
```

### Implementation Steps
1. Create OIDC Identity Provider in AWS
2. Create IAM Role with trust policy for GitHub
3. Configure GitHub Actions to use OIDC
4. No secrets needed in GitHub!

### Cost Breakdown
- **OIDC itself**: FREE
- **Deployment target costs** (same as whatever service you choose)
- No additional costs for OIDC

### Example Workflow
```yaml
- name: Configure AWS credentials
  uses: aws-actions/configure-aws-credentials@v4
  with:
    role-to-assume: arn:aws:iam::123456789:role/GitHubActionsRole
    aws-region: ap-southeast-1

- name: Deploy (no secrets needed!)
  run: |
    aws ecs update-service --cluster my-cluster --service my-service
```

### Pros
- Most secure option
- No credential rotation needed
- Audit trail in AWS CloudTrail
- Works with any AWS service

### Cons
- Initial setup complexity
- Requires understanding IAM roles

---

## Option 3: AWS CodeDeploy

### Overview
Native AWS deployment service that handles deployments to EC2, ECS, or Lambda. Manages rollbacks, health checks, and deployment strategies.

### Architecture
```
GitHub Actions → Upload to S3 → CodeDeploy → Deploy to EC2/ECS
```

### Implementation Steps
1. Install CodeDeploy agent on EC2
2. Create appspec.yml file
3. Define deployment configuration
4. GitHub Actions triggers CodeDeploy

### Cost Breakdown
- **CodeDeploy on EC2**: FREE
- **CodeDeploy on ECS**: $0.02 per on-premises instance update
- **S3 storage**: ~$1-5/month
- **EC2 costs**: Your existing ~$30/month

Total: ~$30-35/month (nearly same as current)

### appspec.yml Example
```yaml
version: 0.0
os: linux
files:
  - source: /
    destination: /home/ubuntu/app
hooks:
  BeforeInstall:
    - location: scripts/stop_containers.sh
  AfterInstall:
    - location: scripts/start_containers.sh
  ValidateService:
    - location: scripts/health_check.sh
```

### Pros
- Native AWS service
- Automatic rollback on failure
- Deployment history
- Works with existing EC2

### Cons
- AWS-specific (vendor lock-in)
- Requires CodeDeploy agent
- More complex than docker-compose

---

## Option 4: Kubernetes on EKS

### Overview
Amazon EKS (Elastic Kubernetes Service) provides managed Kubernetes for container orchestration. Best for complex microservice architectures.

### Architecture
```
GitHub Actions → Build → Push to ECR → kubectl apply → EKS runs pods
```

### Implementation Steps
1. Create EKS cluster
2. Convert docker-compose to Kubernetes manifests
3. Set up ingress controller
4. Configure GitHub Actions with kubectl

### Cost Breakdown
```
EKS Control Plane: $73/month
Worker Nodes (2 × t3.medium): 2 × $30 = $60/month
Load Balancer: $20/month
NAT Gateway: $45/month
Data Transfer: ~$10/month

Total: ~$208/month
```

### Kubernetes Manifest Example
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sensor-data
spec:
  replicas: 2
  selector:
    matchLabels:
      app: sensor-data
  template:
    metadata:
      labels:
        app: sensor-data
    spec:
      containers:
      - name: sensor-data
        image: subhaj888/munbon-sensor-data:latest
        ports:
        - containerPort: 3001
```

### Pros
- Industry standard for container orchestration
- Massive ecosystem
- Advanced features (auto-scaling, self-healing)
- Multi-cloud portable

### Cons
- Steep learning curve
- Most expensive option
- Overkill for simple apps
- Requires Kubernetes expertise

---

## Cost Comparison Summary

| Option | Monthly Cost | Setup Complexity | Operational Complexity |
|--------|-------------|------------------|----------------------|
| Current EC2 | ~$30 | Low | High (manual) |
| ECS Fargate | ~$130-175 | Medium | Low |
| CodeDeploy | ~$35 | Medium | Medium |
| EKS | ~$208+ | High | High |

## Recommendations

### For Your Current Needs (3 services)
**Best Choice: CodeDeploy with existing EC2**
- Minimal cost increase
- Adds deployment safety
- Can migrate to ECS later

### For Future Growth (10+ services)
**Best Choice: ECS with Fargate + GitHub OIDC**
- Scales well
- No server management
- Reasonable cost for production

### For Enterprise/Complex Requirements
**Best Choice: EKS**
- When you need Kubernetes features
- Have dedicated DevOps team
- Running 50+ services

## Migration Path
1. **Immediate**: Fix current deployment with CodeDeploy
2. **3 months**: Implement GitHub OIDC for security
3. **6 months**: Evaluate ECS migration based on growth
4. **Future**: Consider EKS if complexity demands it

## Quick Start Commands

### For ECS Fargate
```bash
# Create ECR repository
aws ecr create-repository --repository-name munbon-sensor-data

# Create ECS cluster
aws ecs create-cluster --cluster-name munbon-backend

# Register task definition
aws ecs register-task-definition --cli-input-json file://task-definition.json
```

### For CodeDeploy
```bash
# Create CodeDeploy application
aws deploy create-application --application-name munbon-backend

# Create deployment group
aws deploy create-deployment-group \
  --application-name munbon-backend \
  --deployment-group-name production \
  --ec2-tag-filters Key=Name,Type=KEY_AND_VALUE,Value=munbon-ec2
```

### For GitHub OIDC
```bash
# Create OIDC provider
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com
```