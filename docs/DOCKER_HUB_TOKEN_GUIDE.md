# How to Create Docker Hub Access Token

## Step-by-Step Guide:

### 1. Go to Docker Hub
- Visit: https://hub.docker.com
- Make sure you're logged in as `subhaj888`

### 2. Access Account Settings
- Click on your username/profile icon in the top-right corner
- Select **"Account Settings"** from the dropdown

### 3. Navigate to Security
- In the left sidebar of Account Settings
- Click on **"Security"**
- Direct link: https://hub.docker.com/settings/security

### 4. Find Access Tokens Section
- On the Security page, look for **"Access Tokens"** section
- You should see a **"New Access Token"** button

### 5. Create New Token
Click **"New Access Token"** and fill in:
- **Access Token Description**: `GitHub Actions Munbon`
- **Access Token Permissions**: Select **"Read, Write, Delete"**
- Click **"Generate"**

### 6. IMPORTANT: Copy the Token
- The token will be shown ONLY ONCE
- Copy it immediately
- Save it somewhere safe temporarily

### 7. Token Format
The token will look something like:
```
dckr_pat_ABC123xyz...
```

## If You Can't Find It:

### Alternative Navigation:
1. Docker Hub home → Click your username (top right)
2. Select "My Account"
3. Click "Security" tab
4. Scroll to "Access Tokens" section

### Direct Links:
- Security page: https://hub.docker.com/settings/security
- If logged in, try: https://hub.docker.com/settings/security?tab=accessToken

## What to Do with the Token:

1. Copy the token
2. Go to GitHub repository settings
3. Add it as a secret named `DOCKERHUB_TOKEN`
4. Never share or commit this token

## Note:
- Personal Access Tokens are more secure than passwords
- They can be revoked without changing your password
- Perfect for CI/CD systems like GitHub Actions