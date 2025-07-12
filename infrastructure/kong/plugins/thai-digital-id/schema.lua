-- Schema definition for Thai Digital ID plugin

local typedefs = require "kong.db.schema.typedefs"

return {
    name = "thai-digital-id",
    fields = {
        {
            consumer = typedefs.no_consumer
        },
        {
            protocols = typedefs.protocols_http
        },
        {
            config = {
                type = "record",
                fields = {
                    {
                        client_id = {
                            type = "string",
                            required = true,
                            description = "Thai Digital ID OAuth client ID"
                        }
                    },
                    {
                        client_secret = {
                            type = "string",
                            required = true,
                            description = "Thai Digital ID OAuth client secret"
                        }
                    },
                    {
                        auth_endpoint = {
                            type = "string",
                            default = "https://api.digitalid.go.th/oauth/authorize",
                            description = "Thai Digital ID authorization endpoint"
                        }
                    },
                    {
                        token_endpoint = {
                            type = "string",
                            default = "https://api.digitalid.go.th/oauth/token",
                            description = "Thai Digital ID token endpoint"
                        }
                    },
                    {
                        userinfo_endpoint = {
                            type = "string",
                            default = "https://api.digitalid.go.th/userinfo",
                            description = "Thai Digital ID userinfo endpoint"
                        }
                    },
                    {
                        redirect_uri = {
                            type = "string",
                            required = true,
                            description = "OAuth redirect URI"
                        }
                    },
                    {
                        scope = {
                            type = "string",
                            default = "openid profile email citizen_id",
                            description = "OAuth scopes to request"
                        }
                    },
                    {
                        jwt_secret = {
                            type = "string",
                            required = true,
                            description = "Secret for JWT validation"
                        }
                    },
                    {
                        timeout = {
                            type = "number",
                            default = 10000,
                            description = "HTTP timeout in milliseconds"
                        }
                    },
                    {
                        cache_ttl = {
                            type = "number",
                            default = 300,
                            description = "Cache TTL in seconds"
                        }
                    },
                    {
                        required_roles = {
                            type = "array",
                            elements = {
                                type = "string"
                            },
                            description = "Required user roles for access"
                        }
                    }
                }
            }
        }
    }
}