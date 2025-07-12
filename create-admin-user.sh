#!/bin/bash

# Script to create initial admin user for Munbon Backend

set -e

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Default values
DEFAULT_EMAIL="admin@munbon.com"
DEFAULT_PASSWORD="Admin123!"
DEFAULT_FIRST_NAME="System"
DEFAULT_LAST_NAME="Administrator"

# Check if auth service is running
if ! curl -s -f http://localhost:3001/health > /dev/null 2>&1; then
    print_error "Auth service is not running on http://localhost:3001"
    echo "Please start the auth service first with: ./start-services.sh"
    exit 1
fi

# Get user input
echo "Create Admin User for Munbon Backend"
echo "===================================="
echo ""

read -p "Email [$DEFAULT_EMAIL]: " EMAIL
EMAIL=${EMAIL:-$DEFAULT_EMAIL}

read -p "Password [$DEFAULT_PASSWORD]: " -s PASSWORD
echo ""
PASSWORD=${PASSWORD:-$DEFAULT_PASSWORD}

read -p "First Name [$DEFAULT_FIRST_NAME]: " FIRST_NAME
FIRST_NAME=${FIRST_NAME:-$DEFAULT_FIRST_NAME}

read -p "Last Name [$DEFAULT_LAST_NAME]: " LAST_NAME
LAST_NAME=${LAST_NAME:-$DEFAULT_LAST_NAME}

# Create admin user via direct database insertion
# First, we need to create a temporary SQL file
cat > /tmp/create_admin_user.sql << EOF
-- Create admin user for Munbon Backend
BEGIN;

-- Insert user
INSERT INTO users (
    id,
    email,
    password,
    first_name,
    last_name,
    user_type,
    is_active,
    is_verified,
    created_at,
    updated_at
) VALUES (
    gen_random_uuid(),
    '$EMAIL',
    '\$2b\$10\$YourHashedPasswordHere', -- This will be replaced
    '$FIRST_NAME',
    '$LAST_NAME',
    'INTERNAL',
    true,
    true,
    NOW(),
    NOW()
) ON CONFLICT (email) DO NOTHING
RETURNING id;

-- Get the user ID
WITH user_info AS (
    SELECT id FROM users WHERE email = '$EMAIL'
)
-- Insert admin role
INSERT INTO user_roles (user_id, role_id)
SELECT 
    u.id,
    r.id
FROM user_info u, roles r
WHERE r.name = 'SYSTEM_ADMIN'
AND NOT EXISTS (
    SELECT 1 FROM user_roles ur 
    WHERE ur.user_id = u.id AND ur.role_id = r.id
);

COMMIT;
EOF

# Use the auth service API to create the user instead
print_warning "Creating admin user via API..."

# First, let's create a registration endpoint call
RESPONSE=$(curl -s -X POST http://localhost:3001/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d "{
    \"email\": \"$EMAIL\",
    \"password\": \"$PASSWORD\",
    \"firstName\": \"$FIRST_NAME\",
    \"lastName\": \"$LAST_NAME\",
    \"userType\": \"INTERNAL\"
  }")

if echo "$RESPONSE" | grep -q "success.*true"; then
    print_success "Admin user created successfully!"
    
    # Now we need to assign admin role
    # First login to get token
    LOGIN_RESPONSE=$(curl -s -X POST http://localhost:3001/api/v1/auth/login \
      -H "Content-Type: application/json" \
      -d "{
        \"email\": \"$EMAIL\",
        \"password\": \"$PASSWORD\"
      }")
    
    TOKEN=$(echo "$LOGIN_RESPONSE" | grep -o '"accessToken":"[^"]*' | cut -d'"' -f4)
    
    if [ -n "$TOKEN" ]; then
        # Get user ID
        USER_ID=$(echo "$LOGIN_RESPONSE" | grep -o '"id":"[^"]*' | cut -d'"' -f4)
        
        print_warning "Assigning SYSTEM_ADMIN role..."
        
        # This would require an admin endpoint to assign roles
        # For now, we'll need to do it manually in the database
        
        print_warning "To complete admin setup, run this SQL in the auth database:"
        echo ""
        echo "UPDATE users SET user_type = 'INTERNAL' WHERE email = '$EMAIL';"
        echo "INSERT INTO user_roles (user_id, role_id)"
        echo "SELECT u.id, r.id FROM users u, roles r"
        echo "WHERE u.email = '$EMAIL' AND r.name = 'SYSTEM_ADMIN';"
        echo ""
    fi
else
    print_error "Failed to create admin user"
    echo "Response: $RESPONSE"
    exit 1
fi

# Clean up
rm -f /tmp/create_admin_user.sql

echo ""
echo "Admin User Details:"
echo "=================="
echo "Email: $EMAIL"
echo "Password: $PASSWORD"
echo ""
print_warning "Please save these credentials securely!"
echo ""
print_success "You can now login at: http://localhost:3000/login"