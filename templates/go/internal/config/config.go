package config

import (
	"os"
)

type Config struct {
	ServiceName string
	Environment string
	Port        string
	LogLevel    string
}

func Load() *Config {
	return &Config{
		ServiceName: getEnv("SERVICE_NAME", "{{SERVICE_NAME}}"),
		Environment: getEnv("ENVIRONMENT", "development"),
		Port:        getEnv("PORT", "8080"),
		LogLevel:    getEnv("LOG_LEVEL", "info"),
	}
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}