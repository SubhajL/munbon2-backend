-- Authentication and User Management Tables

-- Users table
CREATE TABLE IF NOT EXISTS auth.users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    thai_national_id VARCHAR(13) UNIQUE,
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255),
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    phone_number VARCHAR(20),
    user_type VARCHAR(50) NOT NULL CHECK (user_type IN ('farmer', 'operator', 'admin', 'viewer', 'government')),
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    last_login_at TIMESTAMP WITH TIME ZONE,
    failed_login_attempts INTEGER DEFAULT 0,
    locked_until TIMESTAMP WITH TIME ZONE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_email ON auth.users(email);
CREATE INDEX idx_users_thai_national_id ON auth.users(thai_national_id) WHERE thai_national_id IS NOT NULL;

-- Roles table
CREATE TABLE IF NOT EXISTS auth.roles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    role_name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    is_system_role BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Permissions table
CREATE TABLE IF NOT EXISTS auth.permissions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    permission_name VARCHAR(100) UNIQUE NOT NULL,
    resource VARCHAR(100) NOT NULL,
    action VARCHAR(50) NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_permissions_resource_action ON auth.permissions(resource, action);

-- User roles junction table
CREATE TABLE IF NOT EXISTS auth.user_roles (
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    role_id UUID REFERENCES auth.roles(id) ON DELETE CASCADE,
    assigned_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    assigned_by UUID REFERENCES auth.users(id),
    PRIMARY KEY (user_id, role_id)
);

-- Role permissions junction table
CREATE TABLE IF NOT EXISTS auth.role_permissions (
    role_id UUID REFERENCES auth.roles(id) ON DELETE CASCADE,
    permission_id UUID REFERENCES auth.permissions(id) ON DELETE CASCADE,
    granted_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (role_id, permission_id)
);

-- OAuth providers
CREATE TABLE IF NOT EXISTS auth.oauth_providers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    provider_name VARCHAR(50) UNIQUE NOT NULL,
    client_id VARCHAR(255) NOT NULL,
    client_secret VARCHAR(255),
    authorization_url VARCHAR(500),
    token_url VARCHAR(500),
    user_info_url VARCHAR(500),
    scopes TEXT[],
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- OAuth accounts linked to users
CREATE TABLE IF NOT EXISTS auth.oauth_accounts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    provider_id UUID REFERENCES auth.oauth_providers(id),
    provider_user_id VARCHAR(255) NOT NULL,
    access_token TEXT,
    refresh_token TEXT,
    token_expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(provider_id, provider_user_id)
);

-- API keys for service authentication
CREATE TABLE IF NOT EXISTS auth.api_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    key_hash VARCHAR(255) UNIQUE NOT NULL,
    key_prefix VARCHAR(10) NOT NULL, -- First few chars for identification
    name VARCHAR(255) NOT NULL,
    description TEXT,
    service_name VARCHAR(100),
    permissions JSONB DEFAULT '[]',
    rate_limit INTEGER DEFAULT 1000, -- requests per hour
    is_active BOOLEAN DEFAULT TRUE,
    expires_at TIMESTAMP WITH TIME ZONE,
    last_used_at TIMESTAMP WITH TIME ZONE,
    created_by UUID REFERENCES auth.users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_api_keys_key_hash ON auth.api_keys(key_hash);
CREATE INDEX idx_api_keys_service_name ON auth.api_keys(service_name) WHERE service_name IS NOT NULL;

-- Session management
CREATE TABLE IF NOT EXISTS auth.sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    session_token VARCHAR(255) UNIQUE NOT NULL,
    ip_address INET,
    user_agent TEXT,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_sessions_session_token ON auth.sessions(session_token);
CREATE INDEX idx_sessions_user_id ON auth.sessions(user_id);
CREATE INDEX idx_sessions_expires_at ON auth.sessions(expires_at);

-- Audit log for authentication events
CREATE TABLE IF NOT EXISTS auth.audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES auth.users(id),
    event_type VARCHAR(50) NOT NULL,
    event_details JSONB DEFAULT '{}',
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_log_user_id ON auth.audit_log(user_id);
CREATE INDEX idx_audit_log_event_type ON auth.audit_log(event_type);
CREATE INDEX idx_audit_log_created_at ON auth.audit_log(created_at);

-- Insert default roles
INSERT INTO auth.roles (role_name, description, is_system_role) VALUES
    ('super_admin', 'Full system access', true),
    ('admin', 'Administrative access', true),
    ('operator', 'System operator with control permissions', true),
    ('analyst', 'Data analysis and reporting', true),
    ('farmer', 'Farmer with access to own plot data', true),
    ('viewer', 'Read-only access', true)
ON CONFLICT (role_name) DO NOTHING;

-- Insert default permissions
INSERT INTO auth.permissions (permission_name, resource, action, description) VALUES
    ('water_control.gates.read', 'water_control', 'read', 'View gate status'),
    ('water_control.gates.write', 'water_control', 'write', 'Control gates'),
    ('sensor_data.read', 'sensor_data', 'read', 'View sensor data'),
    ('sensor_data.write', 'sensor_data', 'write', 'Update sensor data'),
    ('reports.generate', 'reports', 'generate', 'Generate reports'),
    ('users.manage', 'users', 'manage', 'Manage user accounts'),
    ('system.configure', 'system', 'configure', 'Configure system settings')
ON CONFLICT (permission_name) DO NOTHING;

-- Create triggers
CREATE TRIGGER update_users_modtime 
    BEFORE UPDATE ON auth.users 
    FOR EACH ROW EXECUTE FUNCTION update_modified_column();

CREATE TRIGGER update_roles_modtime 
    BEFORE UPDATE ON auth.roles 
    FOR EACH ROW EXECUTE FUNCTION update_modified_column();

CREATE TRIGGER update_oauth_providers_modtime 
    BEFORE UPDATE ON auth.oauth_providers 
    FOR EACH ROW EXECUTE FUNCTION update_modified_column();

CREATE TRIGGER update_api_keys_modtime 
    BEFORE UPDATE ON auth.api_keys 
    FOR EACH ROW EXECUTE FUNCTION update_modified_column();

-- Grant permissions
GRANT SELECT ON auth.roles, auth.permissions TO munbon_reader;
GRANT ALL ON ALL TABLES IN SCHEMA auth TO munbon_app;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA auth TO munbon_app;