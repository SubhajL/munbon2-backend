# GitHub Secrets Manual Setup

## Step 1: Go to GitHub Secrets Page
Open this link in your browser:
https://github.com/SubhajL/munbon2-backend/settings/secrets/actions

## Step 2: Add EC2_HOST Secret
1. Click "New repository secret"
2. Name: `EC2_HOST`
3. Value: `43.209.22.250`
4. Click "Add secret"

## Step 3: Add EC2_USER Secret
1. Click "New repository secret"
2. Name: `EC2_USER`
3. Value: `ubuntu`
4. Click "Add secret"

## Step 4: Add EC2_SSH_KEY Secret
1. Click "New repository secret"
2. Name: `EC2_SSH_KEY`
3. Value: Copy and paste everything below (including the BEGIN and END lines):

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

4. Click "Add secret"

## Step 5: Verify
After adding all three secrets, you should see:
- EC2_HOST
- EC2_USER  
- EC2_SSH_KEY

Listed in your repository secrets.

## Step 6: Test Deployment
Push any change to trigger deployment:
```bash
git add .
git commit -m "Test GitHub Actions deployment"
git push origin main
```

Then monitor at: https://github.com/SubhajL/munbon2-backend/actions