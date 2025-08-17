# Quick Fix for GitHub Actions Deployment

## The workflow is failing because GitHub Secrets are missing!

### Step 1: Open GitHub Secrets Page
Click this link: https://github.com/SubhajL/munbon2-backend/settings/secrets/actions

### Step 2: Add These 3 Secrets

Click "New repository secret" for each:

#### Secret 1: EC2_HOST
- **Name:** EC2_HOST
- **Secret:** 43.209.22.250

#### Secret 2: EC2_USER
- **Name:** EC2_USER
- **Secret:** ubuntu

#### Secret 3: EC2_SSH_KEY
- **Name:** EC2_SSH_KEY
- **Secret:** (Copy everything below including BEGIN and END lines)
```
-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEAp0oGxofUDL6uMfX3WFeR+n05CqSLZowjLfMeq7Kqnd2E9TBM
oQ6wpGIZDnDK2l5qs2zBmSl7HfaiLPb00jbZb5TqyjbeVCqnsAYFaYiTizCfyJYc
x3U4fDyOGlkZb6+VOvKTG5uUdmJs63GTuwhssDDgpoEQG+cv3eZm2mDIwKrEe7oh
30S6bFAtzBNgJN8wy1cIvqF5lET/kQgvrSTjh3xv4+iH9Mepa+vmF+Bcye6VbTvp
x3oFQxanzXTBIn2nN766O5Cd1LkSbFdg2Oq2nruqdyvxn/0YKLr4F1Ufx/CcqzvG
obmCi/dFK4pmzZwsYDJTwSfw5JFguXPSMhBcAQIDAQABAoIBAGMU1S6BBHcH+ORe
akFInI1f3YkQLABwv+VXObM3/xXBPh56nOhHaxfxgiWraHotscTThVbR2rnEegln
u1lGY0JTUTyzgrsXCHqZFluLKNgn1HtZbXI1W185/nBclVQxCpH/WmHfo+76HMjW
XElKlBVG3cfAaWodY5xp+kEdUcnKZbFxNtSC3wVGQ/lGkuOD2E9DwasRHgJWyt57
Mx24bCtYwfLcYtsqYBnvtJAY0Z9Io6j5frDcyL7+XT69yTrszWEeCTzWN4vo4ec1
LTn+fgyYdqDFV5CHNoOSnY6FawCWMCev72QQ23o/YKh1KNpA4yOA5LZHpUG4+rR5
k6mY2AECgYEAzx5+yWx8jpr0ehPSvjMVOPMvRUWU2+wrGOedP4McnSF5h4WYRz9w
UOuCSIyTWhuAtvXugrcR+gTuTKkoBZRRRmYlk41SQx/R3sIpTStR2h42Y83+7bH5
YMH6b7Tk+SkpdMLPoFabFdyKvCQ74gbreOy8lvYbbWtGe6qynULJq8kCgYEAzsUg
fOv25RA3IUGTEl2x77LTcbMsopfsplz6i4qdoYvBm0J3XUFjnh5h7A4Py6ZyfhzI
Lm9oTA/kNnBPNm7LB+BL1vBODGTp2rU2mFOdIn8bGR6LZ2ZRweHxfPsBZNbomhks
eORWWuJR+hkaEJlAOuoKrrYS39nArrrV1fFN2nkCgYAsDU1kI/neDuEeseap442I
/lg4gJMnr3R/KIwOfSFx3jPN+kEoLjsCSwT7z0Jr8NuQjoA7NxrQtYnFrli/zwr2
UTV+y5kKg9MMcPl920/ed3yT/7VP8wGabceJSM1GnVWe6uxkKudzX+P2HjLKYTRm
FNwLs66juCRWmzjAL/ta2QKBgQCRjnWjWxzv/a1BjP7yg+C544Iz3TUDtL1UE8oQ
J2F2EoMVQAH1NQ3ihnLakL+P1jltC+fjwGuEd/9oT0GECRSGE+Bvi7T1xqhVXRH0
w4+vdBjoYvcxr/bH7L1qBOzjRuJxcF09MUiVLBMXY0pU+v0bPByPBv9cc9bPahkU
RY1PyQKBgEThqLkh2h53fJe0wL5mzGZ4De4Ruhrq/BL9/v0b5YtfMPXaeF2/Z6Li
WnIXxhcRA0Oh/mt2t+tyCI+5ekyaGBfClmQdjFdKxlPmuCeeL1+Jb4jp7GIXbR28
DNgUmBezqQhYK+bUo0ax9xBfNInD7DeAMgVAnToaWXnz1SR7XuST
-----END RSA PRIVATE KEY-----
```

### Step 3: Trigger Deployment Again

After adding all 3 secrets:

1. Go to: https://github.com/SubhajL/munbon2-backend/actions
2. Click on "Deploy to EC2 with Docker" workflow
3. Click "Run workflow" button
4. Select "main" branch
5. Click green "Run workflow" button

### Alternative: Manual Deploy Right Now

While waiting for GitHub Actions, you can deploy manually:

```bash
ssh -i th-lab01.pem ubuntu@43.209.22.250

# Then run:
cd munbon2-backend && git pull && cp .env.ec2 .env && docker-compose -f docker-compose.ec2-consolidated.yml up -d --build
```