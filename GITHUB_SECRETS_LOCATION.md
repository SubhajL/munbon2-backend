# How to Find GitHub Secrets

## Navigate to GitHub Secrets:

1. **Go to your repository**: https://github.com/SubhajL/munbon2-backend

2. **Click on "Settings"** tab at the top of the repository page
   - If you don't see Settings, you might not have admin access
   - Settings is in the top menu bar: Code | Issues | Pull requests | Actions | Projects | Wiki | Security | Insights | **Settings**

3. **In the left sidebar**, look for:
   - Under "Security" section
   - Click on **"Secrets and variables"**
   - Then click on **"Actions"**

4. **Alternative navigation**:
   - Direct URL: https://github.com/SubhajL/munbon2-backend/settings/secrets/actions

## If you can't see Settings:

1. **Check repository permissions**:
   - You need to be the repository owner or have admin access
   - If it's your repository, you should see it

2. **Check if you're logged in**:
   - Make sure you're logged into GitHub
   - Check the top-right corner for your profile picture

## What you should see:

Once in Secrets and variables → Actions:
- **Repository secrets** section
- Button: **"New repository secret"**
- Any existing secrets (names only, values are hidden)

## Adding the secrets:

Click "New repository secret" and add:
1. **Name**: `DOCKERHUB_USERNAME`
   **Value**: `subhaj888`

2. **Name**: `DOCKERHUB_TOKEN`
   **Value**: (Your Docker Hub access token)

## Screenshots of the navigation:
1. Repository page → Settings tab
2. Left sidebar → Secrets and variables → Actions
3. New repository secret button