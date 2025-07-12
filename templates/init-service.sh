#!/bin/bash

# Template initialization script for Munbon microservices
# Usage: ./init-service.sh <language> <service-name> [target-directory]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LANGUAGE=$1
SERVICE_NAME=$2
TARGET_DIR=${3:-"../services/$SERVICE_NAME"}

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Validate inputs
if [ -z "$LANGUAGE" ] || [ -z "$SERVICE_NAME" ]; then
    print_error "Usage: $0 <language> <service-name> [target-directory]"
    print_error "Languages: nodejs-typescript, python-fastapi, go, java-springboot"
    exit 1
fi

# Validate language
case $LANGUAGE in
    nodejs-typescript|python-fastapi|go|java-springboot)
        ;;
    *)
        print_error "Invalid language: $LANGUAGE"
        print_error "Valid languages: nodejs-typescript, python-fastapi, go, java-springboot"
        exit 1
        ;;
esac

# Convert service name to different cases
SERVICE_NAME_LOWER=$(echo "$SERVICE_NAME" | tr '[:upper:]' '[:lower:]')
SERVICE_NAME_UPPER=$(echo "$SERVICE_NAME" | tr '[:lower:]' '[:upper:]')
SERVICE_NAME_CAMEL=$(echo "$SERVICE_NAME" | sed -r 's/(^|-)([a-z])/\U\2/g')

print_status "Initializing $LANGUAGE service: $SERVICE_NAME"
print_status "Target directory: $TARGET_DIR"

# Check if target directory exists
if [ -d "$TARGET_DIR" ]; then
    print_warning "Target directory already exists: $TARGET_DIR"
    read -p "Do you want to overwrite? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_error "Aborted"
        exit 1
    fi
    rm -rf "$TARGET_DIR"
fi

# Copy template
print_status "Copying template files..."
cp -r "$SCRIPT_DIR/$LANGUAGE" "$TARGET_DIR"

# Replace placeholders
print_status "Replacing placeholders..."
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    find "$TARGET_DIR" -type f -name "*.yaml" -o -name "*.yml" -o -name "*.json" -o -name "*.xml" -o -name "*.md" -o -name "*.ts" -o -name "*.js" -o -name "*.py" -o -name "*.go" -o -name "*.java" -o -name "*.sh" -o -name "Dockerfile" | while read file; do
        sed -i '' "s/{{SERVICE_NAME}}/$SERVICE_NAME_LOWER/g" "$file"
        sed -i '' "s/{{SERVICE_NAME_UPPER}}/$SERVICE_NAME_UPPER/g" "$file"
        sed -i '' "s/{{SERVICE_NAME_CAMEL}}/$SERVICE_NAME_CAMEL/g" "$file"
    done
else
    # Linux
    find "$TARGET_DIR" -type f \( -name "*.yaml" -o -name "*.yml" -o -name "*.json" -o -name "*.xml" -o -name "*.md" -o -name "*.ts" -o -name "*.js" -o -name "*.py" -o -name "*.go" -o -name "*.java" -o -name "*.sh" -o -name "Dockerfile" \) -exec sed -i "s/{{SERVICE_NAME}}/$SERVICE_NAME_LOWER/g" {} \;
    find "$TARGET_DIR" -type f \( -name "*.yaml" -o -name "*.yml" -o -name "*.json" -o -name "*.xml" -o -name "*.md" -o -name "*.ts" -o -name "*.js" -o -name "*.py" -o -name "*.go" -o -name "*.java" -o -name "*.sh" -o -name "Dockerfile" \) -exec sed -i "s/{{SERVICE_NAME_UPPER}}/$SERVICE_NAME_UPPER/g" {} \;
    find "$TARGET_DIR" -type f \( -name "*.yaml" -o -name "*.yml" -o -name "*.json" -o -name "*.xml" -o -name "*.md" -o -name "*.ts" -o -name "*.js" -o -name "*.py" -o -name "*.go" -o -name "*.java" -o -name "*.sh" -o -name "Dockerfile" \) -exec sed -i "s/{{SERVICE_NAME_CAMEL}}/$SERVICE_NAME_CAMEL/g" {} \;
fi

# Rename directories for Java packages
if [ "$LANGUAGE" == "java-springboot" ]; then
    print_status "Renaming Java package directories..."
    mv "$TARGET_DIR/src/main/java/com/munbon/{{SERVICE_NAME}}" "$TARGET_DIR/src/main/java/com/munbon/$SERVICE_NAME_LOWER"
    mv "$TARGET_DIR/src/test/java/com/munbon/{{SERVICE_NAME}}" "$TARGET_DIR/src/test/java/com/munbon/$SERVICE_NAME_LOWER"
fi

# Initialize git repository
print_status "Initializing git repository..."
cd "$TARGET_DIR"
git init
git add .
git commit -m "Initial commit for $SERVICE_NAME service"

# Install dependencies based on language
print_status "Installing dependencies..."
case $LANGUAGE in
    nodejs-typescript)
        if command -v npm &> /dev/null; then
            npm install
            print_status "Dependencies installed successfully"
        else
            print_warning "npm not found. Please install Node.js and run 'npm install' manually"
        fi
        ;;
    python-fastapi)
        if command -v poetry &> /dev/null; then
            poetry install
            print_status "Dependencies installed successfully"
        elif command -v pip &> /dev/null; then
            print_warning "Poetry not found. Using pip instead..."
            pip install -r requirements.txt
        else
            print_warning "Neither poetry nor pip found. Please install dependencies manually"
        fi
        ;;
    go)
        if command -v go &> /dev/null; then
            go mod download
            print_status "Dependencies downloaded successfully"
        else
            print_warning "Go not found. Please install Go and run 'go mod download' manually"
        fi
        ;;
    java-springboot)
        if command -v mvn &> /dev/null; then
            mvn dependency:go-offline
            print_status "Dependencies downloaded successfully"
        else
            print_warning "Maven not found. Please install Maven and run 'mvn dependency:go-offline' manually"
        fi
        ;;
esac

print_status "Service initialization complete!"
print_status "Next steps:"
echo "  1. cd $TARGET_DIR"
echo "  2. Review and update the README.md"
echo "  3. Update configuration files as needed"
echo "  4. Start developing your service!"

# Print language-specific instructions
case $LANGUAGE in
    nodejs-typescript)
        echo ""
        echo "  Run locally: npm run dev"
        echo "  Build: npm run build"
        echo "  Test: npm test"
        ;;
    python-fastapi)
        echo ""
        echo "  Run locally: poetry run uvicorn app.main:app --reload"
        echo "  Test: poetry run pytest"
        ;;
    go)
        echo ""
        echo "  Run locally: go run cmd/server/main.go"
        echo "  Build: go build -o bin/server cmd/server/main.go"
        echo "  Test: go test ./..."
        ;;
    java-springboot)
        echo ""
        echo "  Run locally: mvn spring-boot:run"
        echo "  Build: mvn clean package"
        echo "  Test: mvn test"
        ;;
esac