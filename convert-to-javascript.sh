#!/bin/bash

# Script to convert TypeScript services to JavaScript for development
# This keeps the compiled JavaScript from dist folder and adds module-alias support

SERVICE_NAME=$1

if [ -z "$SERVICE_NAME" ]; then
    echo "Usage: ./convert-to-javascript.sh <service-name>"
    echo "Example: ./convert-to-javascript.sh gis"
    exit 1
fi

SERVICE_DIR="/Users/subhajlimanond/dev/munbon2-backend/services/$SERVICE_NAME"

if [ ! -d "$SERVICE_DIR" ]; then
    echo "Service directory not found: $SERVICE_DIR"
    exit 1
fi

cd "$SERVICE_DIR"

echo "Converting $SERVICE_NAME service to JavaScript..."

# Check if dist folder exists
if [ ! -d "dist" ]; then
    echo "Error: dist folder not found. Please build the TypeScript project first with 'npm run build'"
    exit 1
fi

# Backup TypeScript source
echo "1. Backing up TypeScript source..."
if [ -d "src-typescript-backup" ]; then
    echo "   Backup already exists, skipping..."
else
    cp -r src src-typescript-backup
fi

# Remove current src and copy from dist
echo "2. Replacing src with compiled JavaScript..."
rm -rf src
cp -r dist src

# Update package.json
echo "3. Updating package.json..."
cp package.json package.json.backup

# Create a temporary Node.js script to update package.json
cat > update-package.js << 'EOF'
const fs = require('fs');
const pkg = JSON.parse(fs.readFileSync('package.json', 'utf8'));

// Update main entry point
pkg.main = 'src/index.js';

// Update scripts
pkg.scripts.dev = 'nodemon src/index.js';
pkg.scripts.start = 'node src/index.js';

// Remove TypeScript-specific scripts
delete pkg.scripts.build;
delete pkg.scripts['type-check'];

// Update test script if it uses ts-jest
if (pkg.scripts.test && pkg.scripts.test.includes('jest')) {
    pkg.scripts.test = 'jest';
}

// Update lint script
if (pkg.scripts.lint) {
    pkg.scripts.lint = 'eslint src --ext .js';
}
if (pkg.scripts['lint:fix']) {
    pkg.scripts['lint:fix'] = 'eslint src --ext .js --fix';
}

// Update queue processor if exists
if (pkg.scripts['queue:processor']) {
    pkg.scripts['queue:processor'] = pkg.scripts['queue:processor'].replace('ts-node', 'node').replace('.ts', '.js');
}

// Add module-alias to dependencies if not already present
if (!pkg.dependencies['module-alias']) {
    pkg.dependencies['module-alias'] = '^2.2.3';
}

// Add _moduleAliases configuration
pkg._moduleAliases = {
    '@config': 'src/config',
    '@controllers': 'src/controllers',
    '@services': 'src/services',
    '@routes': 'src/routes',
    '@utils': 'src/utils',
    '@middleware': 'src/middleware',
    '@models': 'src/models',
    '@validators': 'src/validators',
    '@workers': 'src/workers',
    '@interfaces': 'src/interfaces',
    '@entities': 'src/entities',
    '@repositories': 'src/repositories'
};

// Move TypeScript dependencies to a backup object
pkg.typescriptDependencies = {};
const tsDevDeps = ['typescript', 'ts-node', 'ts-jest', 'tsx', '@types/', '@typescript-eslint/'];
Object.keys(pkg.devDependencies || {}).forEach(dep => {
    if (tsDevDeps.some(tsDep => dep.includes(tsDep))) {
        pkg.typescriptDependencies[dep] = pkg.devDependencies[dep];
        delete pkg.devDependencies[dep];
    }
});

fs.writeFileSync('package.json', JSON.stringify(pkg, null, 2) + '\n');
console.log('package.json updated successfully');
EOF

node update-package.js
rm update-package.js

# Add module-alias registration to index.js
echo "4. Adding module-alias registration..."
if [ -f "src/index.js" ]; then
    # Create a temporary file with the module-alias registration
    echo '"use strict";' > src/index.js.tmp
    echo "// Register module aliases first" >> src/index.js.tmp
    echo "require('module-alias/register');" >> src/index.js.tmp
    echo "" >> src/index.js.tmp
    
    # Skip the first line if it's "use strict" and append the rest
    if head -n1 src/index.js | grep -q '"use strict"'; then
        tail -n +2 src/index.js >> src/index.js.tmp
    else
        cat src/index.js >> src/index.js.tmp
    fi
    
    mv src/index.js.tmp src/index.js
fi

# Create nodemon.json if it doesn't exist
echo "5. Creating nodemon configuration..."
if [ ! -f "nodemon.json" ]; then
    cat > nodemon.json << 'EOF'
{
  "watch": ["src"],
  "ext": "js,json",
  "ignore": ["src/**/*.spec.js", "src/**/*.test.js"],
  "exec": "node"
}
EOF
fi

# Create .eslintrc.js for JavaScript
echo "6. Creating ESLint configuration..."
cat > .eslintrc.js << 'EOF'
module.exports = {
  env: {
    es2021: true,
    node: true,
    jest: true
  },
  extends: ['eslint:recommended'],
  parserOptions: {
    ecmaVersion: 'latest',
    sourceType: 'module'
  },
  rules: {
    'no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
    'no-console': 'off',
    'prefer-const': 'error'
  }
};
EOF

# Install module-alias if needed
echo "7. Installing module-alias..."
if ! grep -q "module-alias" package.json; then
    npm install module-alias
else
    npm install
fi

echo ""
echo "✅ Conversion complete for $SERVICE_NAME service!"
echo ""
echo "The service has been converted to JavaScript."
echo "- TypeScript source backed up to: src-typescript-backup/"
echo "- Compiled JavaScript is now in: src/"
echo "- package.json has been updated"
echo "- Module aliases configured"
echo ""
echo "To run the service:"
echo "  cd services/$SERVICE_NAME"
echo "  npm run dev"
echo ""
echo "Note: The service may fail to start if it requires a database connection."