#!/bin/bash

echo "Converting TypeScript service to JavaScript..."

# Step 1: Backup original source
echo "Step 1: Backing up original TypeScript source..."
if [ ! -d "src_typescript_backup" ]; then
    cp -r src src_typescript_backup
    echo "✓ Backup created: src_typescript_backup"
else
    echo "✓ Backup already exists"
fi

# Step 2: Clean build and reinstall
echo -e "\nStep 2: Cleaning and rebuilding..."
rm -rf dist node_modules package-lock.json
npm install
npm run build

# Step 3: Replace src with compiled JavaScript
echo -e "\nStep 3: Replacing src with compiled JavaScript..."
rm -rf src
cp -r dist src

# Step 4: Clean up TypeScript artifacts
echo -e "\nStep 4: Cleaning up TypeScript artifacts..."
find src -name "*.d.ts" -delete
find src -name "*.d.ts.map" -delete
find src -name "*.js.map" -delete

# Step 5: Fix imports and exports
echo -e "\nStep 5: Fixing imports and exports..."
node - <<'EOF'
const fs = require('fs');
const path = require('path');

function convertFile(filePath) {
    let content = fs.readFileSync(filePath, 'utf8');
    
    // Remove TypeScript generated code
    content = content.replace(/"use strict";\s*/g, '');
    content = content.replace(/Object\.defineProperty\(exports, "__esModule"[^;]+;\s*/g, '');
    content = content.replace(/var __[a-zA-Z]+\s*=\s*\(this && this\.__[a-zA-Z]+\)[^;]+;/g, '');
    
    // Remove all the TypeScript helper functions
    const helperPattern = /var __\w+\s*=\s*\([^}]+\}\);/gs;
    content = content.replace(helperPattern, '');
    
    // Fix simple imports
    content = content.replace(/const (\w+) = __importDefault\(require\(([^)]+)\)\);/g, 'const $1 = require($2);');
    content = content.replace(/const (\w+) = require\(([^)]+)\)\.default;/g, 'const $1 = require($2);');
    
    // Fix usage of _1 suffix
    content = content.replace(/(\w+)_1\.default/g, '$1');
    content = content.replace(/(\w+)_1/g, '$1');
    
    // Fix (0, function) patterns
    content = content.replace(/\(0, (\w+)\.(\w+)\)/g, '$1.$2');
    
    // Fix exports
    content = content.replace(/exports\.default = (\w+);/g, 'module.exports = $1;');
    
    // Remove source maps
    content = content.replace(/\/\/# sourceMappingURL=.+$/gm, '');
    
    // Clean up
    content = content.replace(/\n\s*\n\s*\n/g, '\n\n');
    
    fs.writeFileSync(filePath, content.trim() + '\n');
}

function processDir(dir) {
    const files = fs.readdirSync(dir);
    files.forEach(file => {
        const fullPath = path.join(dir, file);
        if (fs.statSync(fullPath).isDirectory()) {
            processDir(fullPath);
        } else if (file.endsWith('.js')) {
            console.log('Processing:', fullPath);
            convertFile(fullPath);
        }
    });
}

processDir('./src');
EOF

echo -e "\n✓ Conversion complete!"