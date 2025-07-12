#!/bin/bash

# Security scanning script for Docker images
# Uses Trivy for vulnerability scanning

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_status() {
    echo -e "${GREEN}[SCAN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Install Trivy if not present
install_trivy() {
    if ! command -v trivy &> /dev/null; then
        print_warning "Trivy not found. Installing..."
        brew install aquasecurity/trivy/trivy
    fi
}

# Scan a single image
scan_image() {
    local image=$1
    local severity=${2:-"HIGH,CRITICAL"}
    
    print_status "Scanning $image for $severity vulnerabilities..."
    
    trivy image \
        --severity "$severity" \
        --ignore-unfixed \
        --format table \
        --ignorefile "$PROJECT_ROOT/.trivyignore" \
        "$image"
    
    local exit_code=$?
    
    if [ $exit_code -eq 0 ]; then
        print_status "$image: No $severity vulnerabilities found ✓"
    else
        print_error "$image: Vulnerabilities found!"
        return $exit_code
    fi
}

# Scan all local images
scan_all_images() {
    local severity=${1:-"HIGH,CRITICAL"}
    local registry="localhost:5000"
    local failed=0
    
    print_status "Scanning all images for $severity vulnerabilities..."
    
    # Get all images from local registry
    local images=$(docker images | grep "$registry/munbon" | awk '{print $1":"$2}')
    
    if [ -z "$images" ]; then
        print_warning "No images found in local registry"
        return 0
    fi
    
    for image in $images; do
        if ! scan_image "$image" "$severity"; then
            ((failed++))
        fi
        echo
    done
    
    if [ $failed -gt 0 ]; then
        print_error "Scan completed with $failed images having vulnerabilities"
        return 1
    else
        print_status "All images passed security scan ✓"
        return 0
    fi
}

# Generate security report
generate_report() {
    local output_dir="$PROJECT_ROOT/security-reports"
    local report_file="$output_dir/scan-report-$(date +%Y%m%d-%H%M%S).json"
    
    mkdir -p "$output_dir"
    
    print_status "Generating security report..."
    
    local images=$(docker images | grep "localhost:5000/munbon" | awk '{print $1":"$2}')
    
    echo "{" > "$report_file"
    echo "  \"scan_date\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"," >> "$report_file"
    echo "  \"images\": {" >> "$report_file"
    
    local first=true
    for image in $images; do
        if [ "$first" = false ]; then
            echo "," >> "$report_file"
        fi
        first=false
        
        echo -n "    \"$image\": " >> "$report_file"
        trivy image --format json --quiet "$image" >> "$report_file" 2>/dev/null || echo "{}" >> "$report_file"
    done
    
    echo "  }" >> "$report_file"
    echo "}" >> "$report_file"
    
    print_status "Report saved to: $report_file"
}

# Main execution
main() {
    install_trivy
    
    case "${1:-scan}" in
        scan)
            scan_all_images "${2:-HIGH,CRITICAL}"
            ;;
        report)
            generate_report
            ;;
        image)
            if [ -z "$2" ]; then
                print_error "Please specify an image to scan"
                exit 1
            fi
            scan_image "$2" "${3:-HIGH,CRITICAL}"
            ;;
        *)
            echo "Usage: $0 [scan|report|image] [options]"
            echo "  scan [SEVERITY]     - Scan all images (default: HIGH,CRITICAL)"
            echo "  report             - Generate JSON security report"
            echo "  image IMAGE [SEV]  - Scan specific image"
            exit 1
            ;;
    esac
}

main "$@"