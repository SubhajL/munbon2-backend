# Build stage
FROM golang:1.21-alpine AS builder

# Install build dependencies
RUN apk add --no-cache git ca-certificates tzdata

WORKDIR /app

# Copy go mod files
COPY go.mod go.sum ./

# Download dependencies
RUN go mod download

# Copy source code
COPY . .

# Build the application with optimizations
RUN CGO_ENABLED=0 GOOS=linux GOARCH=arm64 \
    go build -ldflags="-w -s" -a -installsuffix cgo -o main ./cmd/server

# Production stage - using distroless for minimal attack surface
FROM gcr.io/distroless/static:nonroot AS production

# Copy timezone data
COPY --from=builder /usr/share/zoneinfo /usr/share/zoneinfo

# Copy the binary
COPY --from=builder /app/main /app/main

# Use non-root user (65532)
USER nonroot:nonroot

# Expose port
EXPOSE 8080

# Health check (using the binary itself)
HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
  CMD ["/app/main", "-health-check"]

# Run the binary
ENTRYPOINT ["/app/main"]

# Development stage with hot-reload
FROM golang:1.21-alpine AS development

# Install development tools
RUN apk add --no-cache git make

# Install air for hot-reload
RUN go install github.com/cosmtrek/air@latest

WORKDIR /app

# Copy go mod files
COPY go.mod go.sum ./

# Download dependencies
RUN go mod download

# Expose port
EXPOSE 8080

# Development command with hot-reload
CMD ["air", "-c", ".air.toml"]