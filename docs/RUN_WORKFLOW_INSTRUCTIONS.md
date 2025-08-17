# How to Run the Docker Simple Test Workflow

## Direct Method:
1. Go to: https://github.com/SubhajL/munbon2-backend/actions/workflows/docker-simple-test.yml
2. Click "Run workflow" button (top right)
3. Click green "Run workflow" in the dropdown

## If Direct Link Doesn't Work:
1. Go to: https://github.com/SubhajL/munbon2-backend/actions
2. Look for "Docker Simple Test" in the workflows list
3. If not visible, check "All workflows" section
4. Click on the workflow name
5. Click "Run workflow"

## Alternative - Check via GitHub CLI:
```bash
gh workflow list
gh workflow run docker-simple-test.yml
```

## What This Workflow Does:
- Tests GitHub Actions is working
- Verifies Docker Hub credentials
- Takes only 1-2 minutes to complete
- Shows clear success/failure messages

Once this test passes, we'll run the full expert workflow to build all services.