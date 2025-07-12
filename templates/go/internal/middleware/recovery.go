package middleware

import (
	"encoding/json"
	"log"
	"net/http"
	"runtime/debug"
)

// ErrorResponse represents an error response
type ErrorResponse struct {
	Error   string `json:"error"`
	Message string `json:"message"`
}

// Recovery middleware recovers from panics and returns 500 error
func Recovery(logger *log.Logger) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			defer func() {
				if err := recover(); err != nil {
					logger.Printf("panic recovered: %v\n%s", err, debug.Stack())

					w.Header().Set("Content-Type", "application/json")
					w.WriteHeader(http.StatusInternalServerError)

					response := ErrorResponse{
						Error:   "internal_server_error",
						Message: "An internal server error occurred",
					}
					json.NewEncoder(w).Encode(response)
				}
			}()

			next.ServeHTTP(w, r)
		})
	}
}