package config

import (
	"os"
	"strconv"
)

// getEnv gets an environment variable with a fallback value
func getEnv(key, fallback string) string {
	if value, exists := os.LookupEnv(key); exists {
		return value
	}
	return fallback
}

// getEnvInt gets an environment variable as int with a fallback value
func getEnvInt(key string, fallback int) int {
	strValue := getEnv(key, "")
	if strValue == "" {
		return fallback
	}
	if intValue, err := strconv.Atoi(strValue); err == nil {
		return intValue
	}
	return fallback
}

// getEnvBool gets an environment variable as bool with a fallback value
func getEnvBool(key string, fallback bool) bool {
	strValue := getEnv(key, "")
	if strValue == "" {
		return fallback
	}
	if boolValue, err := strconv.ParseBool(strValue); err == nil {
		return boolValue
	}
	return fallback
}