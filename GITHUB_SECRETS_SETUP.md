# GitHub Secrets Setup for EC2 Deployment

## Add these secrets to your GitHub repository:

1. Go to: https://github.com/SubhajL/munbon2-backend
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret** for each of these:

### Secret 1: EC2_HOST
```
43.209.12.182
```

### Secret 2: EC2_USER
```
ubuntu
```

### Secret 3: EC2_SSH_KEY
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

## After adding secrets:

1. Any push to `main` branch will automatically deploy to EC2
2. You can also manually trigger deployment from Actions tab

## Test manual deployment first (optional):
```bash
./scripts/deploy-to-ec2.sh 43.209.12.182 /Users/subhajlimanond/dev/munbon2-backend/th-lab01.pem
```