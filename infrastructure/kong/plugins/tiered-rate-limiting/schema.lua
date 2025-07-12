-- Schema definition for Tiered Rate Limiting plugin

local typedefs = require "kong.db.schema.typedefs"

return {
    name = "tiered-rate-limiting",
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
                        tiers = {
                            type = "map",
                            keys = {
                                type = "string"
                            },
                            values = {
                                type = "record",
                                fields = {
                                    {
                                        minute = {
                                            type = "number",
                                            gt = 0,
                                            description = "Requests per minute"
                                        }
                                    },
                                    {
                                        hour = {
                                            type = "number",
                                            gt = 0,
                                            description = "Requests per hour"
                                        }
                                    },
                                    {
                                        day = {
                                            type = "number",
                                            gt = 0,
                                            description = "Requests per day"
                                        }
                                    }
                                }
                            },
                            default = {
                                guest = {
                                    minute = 10,
                                    hour = 100,
                                    day = 1000
                                },
                                basic = {
                                    minute = 60,
                                    hour = 1000,
                                    day = 10000
                                },
                                premium = {
                                    minute = 200,
                                    hour = 5000,
                                    day = 50000
                                },
                                enterprise = {
                                    minute = 1000,
                                    hour = 20000,
                                    day = 200000
                                },
                                government = {
                                    minute = 2000,
                                    hour = 50000,
                                    day = 500000
                                }
                            }
                        }
                    },
                    {
                        role_mapping = {
                            type = "map",
                            keys = {
                                type = "string"
                            },
                            values = {
                                type = "array",
                                elements = {
                                    type = "string"
                                }
                            },
                            description = "Map roles to tiers"
                        }
                    },
                    {
                        redis_host = {
                            type = "string",
                            default = "redis",
                            description = "Redis host"
                        }
                    },
                    {
                        redis_port = {
                            type = "number",
                            default = 6379,
                            description = "Redis port"
                        }
                    },
                    {
                        redis_password = {
                            type = "string",
                            description = "Redis password"
                        }
                    },
                    {
                        redis_database = {
                            type = "number",
                            default = 0,
                            description = "Redis database"
                        }
                    },
                    {
                        redis_timeout = {
                            type = "number",
                            default = 2000,
                            description = "Redis timeout in milliseconds"
                        }
                    },
                    {
                        fault_tolerant = {
                            type = "boolean",
                            default = true,
                            description = "Continue if Redis is unavailable"
                        }
                    },
                    {
                        hide_client_headers = {
                            type = "boolean",
                            default = false,
                            description = "Hide rate limit headers from client"
                        }
                    }
                }
            }
        }
    }
}