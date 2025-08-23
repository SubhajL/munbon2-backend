#!/bin/bash

# Universal TypeScript to JavaScript converter for Munbon services
# Usage: ./convert-ts-to-js-universal.sh <service-name>

SERVICE_NAME=$1

if [ -z "$SERVICE_NAME" ]; then
    echo "Usage: $0 <service-name>"
    echo "Example: $0 auth"
    exit 1
fi

SERVICE_PATH="services/$SERVICE_NAME"

if [ ! -d "$SERVICE_PATH" ]; then
    echo "Error: Service directory '$SERVICE_PATH' not found"
    exit 1
fi

if [ ! -f "$SERVICE_PATH/tsconfig.json" ]; then
    echo "Error: Service '$SERVICE_NAME' is not a TypeScript project"
    exit 1
fi

if [ -d "$SERVICE_PATH/src_typescript_backup" ]; then
    echo "Service '$SERVICE_NAME' appears to be already converted"
    echo "Backup directory exists: $SERVICE_PATH/src_typescript_backup"
    exit 0
fi

echo "Converting $SERVICE_NAME from TypeScript to JavaScript..."
cd "$SERVICE_PATH"

# Step 1: Backup original source
echo "Step 1: Backing up original TypeScript source..."
cp -r src src_typescript_backup
echo "✓ Backup created: src_typescript_backup"

# Step 2: Clean build and reinstall
echo -e "\nStep 2: Cleaning and rebuilding..."
rm -rf dist node_modules package-lock.json
npm install
npm run build

# Step 3: Replace src with compiled JavaScript
echo -e "\nStep 3: Replacing src with compiled JavaScript..."
rm -rf src
cp -r dist src

# Step 4: Update package.json to point to JavaScript
echo -e "\nStep 4: Updating package.json..."
node -e "
const fs = require('fs');
const pkg = JSON.parse(fs.readFileSync('package.json', 'utf8'));

// Update main entry point
if (pkg.main) {
    pkg.main = pkg.main.replace('dist/', 'src/').replace('.ts', '.js');
}

// Update scripts
if (pkg.scripts) {
    // Update start script
    if (pkg.scripts.start) {
        pkg.scripts.start = pkg.scripts.start.replace('ts-node', 'node').replace('.ts', '.js');
    }
    // Update dev script
    if (pkg.scripts.dev) {
        pkg.scripts.dev = pkg.scripts.dev.replace('ts-node-dev', 'nodemon').replace('tsx watch', 'nodemon');
        pkg.scripts.dev = pkg.scripts.dev.replace('.ts', '.js');
    }
    // Remove build script as it's no longer needed
    delete pkg.scripts.build;
}

// Remove TypeScript dependencies from regular dependencies if they exist there
const tsDepsList = ['typescript', '@types/node', '@types/express', 'ts-node', 'ts-node-dev', 'tsx'];
tsDepsList.forEach(dep => {
    if (pkg.dependencies && pkg.dependencies[dep]) {
        delete pkg.dependencies[dep];
    }
});

fs.writeFileSync('package.json', JSON.stringify(pkg, null, 2) + '\n');
console.log('✓ package.json updated');
"

# Step 5: Create nodemon.json if it doesn't exist
if [ ! -f "nodemon.json" ]; then
    echo -e "\nStep 5: Creating nodemon.json..."
    cat > nodemon.json << 'EOF'
{
  "watch": ["src"],
  "ext": "js,json",
  "ignore": ["src/**/*.spec.js", "node_modules"],
  "exec": "node"
}
EOF
    echo "✓ nodemon.json created"
fi

# Step 6: Install nodemon if needed
echo -e "\nStep 6: Installing nodemon..."
npm install --save-dev nodemon

# Step 7: Clean up TypeScript config files (but keep them for reference)
echo -e "\nStep 7: Archiving TypeScript config files..."
mkdir -p typescript_config_backup
mv tsconfig*.json typescript_config_backup/ 2>/dev/null || true
echo "✓ TypeScript config files archived"

echo -e "\n✅ Conversion complete for $SERVICE_NAME!"
echo "Original TypeScript source: $SERVICE_PATH/src_typescript_backup"
echo "JavaScript source: $SERVICE_PATH/src"

# Return to original directory
cd - > /dev/null