# TLS/SSL Configuration Guide for Munbon API

## Current HTTPS Endpoint
Yes, the API is already accessible via HTTPS at:
```
https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/munbon-m2m-moisture/telemetry
```

## Required TLS/SSL Configuration

### TLS/SSL Versions
- SSL 3.0
- TLS 1.0
- TLS 1.1
- TLS 1.2

### Required Cipher Suites
- TLS_RSA_WITH_AES_256_CBC_SHA
- TLS_RSA_WITH_AES_128_CBC_SHA
- TLS_RSA_WITH_RC4_128_SHA
- TLS_RSA_WITH_RC4_128_MD5
- TLS_RSA_WITH_3DES_EDE_CBC_SHA
- TLS_RSA_WITH_AES_256_CBC_SHA256

## Implementation Options

### Option 1: API Gateway with Custom Domain (Recommended)
AWS API Gateway supports TLS 1.0, 1.1, and 1.2 via security policies.

```bash
# Create custom domain with TLS 1.0 support
aws apigateway create-domain-name \
    --domain-name api.munbon.yourcompany.com \
    --regional-certificate-arn arn:aws:acm:ap-southeast-1:YOUR_ACCOUNT:certificate/YOUR_CERT_ID \
    --endpoint-configuration types=REGIONAL \
    --security-policy TLS_1_0 \
    --region ap-southeast-1
```

**Note**: API Gateway doesn't support SSL 3.0 or custom cipher suite selection.

### Option 2: Application Load Balancer (ALB)
For full control over cipher suites, use ALB with a custom SSL policy.

1. Deploy ALB in front of API Gateway
2. Configure custom SSL policy:

```bash
# Create custom SSL policy
aws elbv2 create-ssl-policy \
    --name munbon-custom-ssl-policy \
    --ssl-protocols SSLv3 TLSv1 TLSv1.1 TLSv1.2 \
    --ciphers \
        AES256-SHA \
        AES128-SHA \
        RC4-SHA \
        RC4-MD5 \
        DES-CBC3-SHA \
        AES256-SHA256
```

### Option 3: CloudFront Distribution
Use CloudFront for global distribution with TLS configuration:

```yaml
ViewerCertificate:
  CloudFrontDefaultCertificate: false
  AcmCertificateArn: !Ref CertificateArn
  SslSupportMethod: sni-only
  MinimumProtocolVersion: SSLv3
```

## Current Limitations

1. **API Gateway Native Support**:
   - ✅ Supports TLS 1.0, 1.1, 1.2
   - ❌ Doesn't support SSL 3.0
   - ❌ Cannot specify individual cipher suites

2. **Security Considerations**:
   - SSL 3.0 and RC4 ciphers are considered insecure
   - AWS deprecated SSL 3.0 support in most services
   - Consider security implications before enabling older protocols

## Deployment Steps

### Step 1: Deploy with TLS 1.0+ (API Gateway)
```bash
cd /Users/subhajlimanond/dev/munbon2-backend/services/sensor-data/deployments/aws-lambda
./deploy-with-custom-tls.sh dev ap-southeast-1 api.munbon.example.com arn:aws:acm:...
```

### Step 2: For SSL 3.0 Support (Use ALB/CloudFront)
Deploy the CloudFormation template:
```bash
aws cloudformation deploy \
    --template-file custom-tls-config.yml \
    --stack-name munbon-tls-config \
    --capabilities CAPABILITY_IAM
```

## Testing TLS Configuration

### Test current endpoint:
```bash
# Check supported TLS versions and ciphers
nmap --script ssl-enum-ciphers -p 443 c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com

# OpenSSL test
openssl s_client -connect c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com:443 -tls1
```

### Test specific cipher:
```bash
openssl s_client -connect YOUR_ENDPOINT:443 -cipher AES256-SHA -tls1
```

## Security Warnings

⚠️ **Important Security Considerations**:
1. **SSL 3.0**: Vulnerable to POODLE attack
2. **RC4 Ciphers**: Cryptographically broken
3. **MD5**: Weak hash algorithm
4. **3DES**: Deprecated due to Sweet32 attack

These older protocols/ciphers are being requested but pose security risks. Consider if newer, more secure alternatives can be used instead.

## Alternative Secure Configuration

If security requirements allow, consider this more secure configuration:
- TLS 1.2 and 1.3 only
- Modern cipher suites:
  - TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384
  - TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256
  - TLS_RSA_WITH_AES_256_GCM_SHA384
  - TLS_RSA_WITH_AES_128_GCM_SHA256