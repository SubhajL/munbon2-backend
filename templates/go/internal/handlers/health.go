package handlers

import (
	"encoding/json"
	"net/http"
	"time"
)

// HealthResponse represents the health check response
type HealthResponse struct {
	Status    string            `json:"status"`
	Service   string            `json:"service"`
	Version   string            `json:"version"`
	Timestamp time.Time         `json:"timestamp"`
	Checks    map[string]string `json:"checks,omitempty"`
}

// HealthHandler handles health check requests
type HealthHandler struct {
	ServiceName string
	Version     string
}

// NewHealthHandler creates a new health handler
func NewHealthHandler(serviceName, version string) *HealthHandler {
	return &HealthHandler{
		ServiceName: serviceName,
		Version:     version,
	}
}

// Health handles the /health endpoint
func (h *HealthHandler) Health(w http.ResponseWriter, r *http.Request) {
	response := HealthResponse{
		Status:    "healthy",
		Service:   h.ServiceName,
		Version:   h.Version,
		Timestamp: time.Now().UTC(),
		Checks: map[string]string{
			"database": "ok",
			"cache":    "ok",
		},
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(response)
}

// Ready handles the /ready endpoint
func (h *HealthHandler) Ready(w http.ResponseWriter, r *http.Request) {
	// Add readiness checks here (e.g., database connections, dependencies)
	response := HealthResponse{
		Status:    "ready",
		Service:   h.ServiceName,
		Version:   h.Version,
		Timestamp: time.Now().UTC(),
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(response)
}