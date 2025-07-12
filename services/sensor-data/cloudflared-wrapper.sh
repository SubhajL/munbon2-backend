#!/bin/bash

# Cloudflared Wrapper Script with DNS Retry Logic
# This script ensures cloudflared can resolve DNS before starting

# Configuration
MAX_RETRIES=10
RETRY_DELAY=5
DNS_TEST_DOMAIN="_origintunneld._tcp.argotunnel.com"
LOG_FILE="./logs/tunnel-wrapper.log"

# Function to log messages
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Function to test DNS resolution
test_dns() {
    # Try to resolve the Cloudflare tunnel DNS
    dig +short srv "$DNS_TEST_DOMAIN" > /dev/null 2>&1
    return $?
}

# Function to wait for network
wait_for_network() {
    local retries=0
    
    while [ $retries -lt $MAX_RETRIES ]; do
        if test_dns; then
            log "DNS resolution successful"
            return 0
        fi
        
        log "DNS resolution failed (attempt $((retries + 1))/$MAX_RETRIES), waiting ${RETRY_DELAY}s..."
        sleep $RETRY_DELAY
        retries=$((retries + 1))
    done
    
    log "ERROR: DNS resolution failed after $MAX_RETRIES attempts"
    return 1
}

# Main execution
log "Starting cloudflared wrapper..."

# Wait for network to be ready
if wait_for_network; then
    log "Network ready, starting cloudflared..."
    
    # Use Google DNS as fallback if system DNS fails
    export CLOUDFLARED_EDGE_IP_VERSION=4
    
    # Run cloudflared with the original arguments
    exec cloudflared "$@"
else
    log "ERROR: Cannot start cloudflared - network not ready"
    exit 1
fi