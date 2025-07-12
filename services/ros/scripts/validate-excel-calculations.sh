#!/bin/bash

# ROS Excel Validation Script
# This script validates that ROS service calculations match Excel exactly

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$SCRIPT_DIR/.."

echo "🔍 ROS Excel Validation Test Suite"
echo "=================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Step 1: Check if Excel file exists
EXCEL_FILE="$PROJECT_ROOT/tests/fixtures/ROS_Calculation.xlsx"
if [ ! -f "$EXCEL_FILE" ]; then
    echo -e "${YELLOW}⚠️  Warning: Excel file not found at $EXCEL_FILE${NC}"
    echo "Please place the ROS Excel worksheet in tests/fixtures/"
    exit 1
fi

# Step 2: Extract test data from Excel
echo "📊 Step 1: Extracting test data from Excel..."
npm run extract-excel-data -- "$EXCEL_FILE"
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Failed to extract Excel data${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Excel data extracted successfully${NC}"
echo ""

# Step 3: Run unit tests for Excel validation
echo "🧪 Step 2: Running Excel validation unit tests..."
npm run test:excel-validation
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Excel validation tests failed${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Unit tests passed${NC}"
echo ""

# Step 4: Run comparison tool
echo "📊 Step 3: Running detailed comparison..."
npm run compare-excel -- --format=both
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Comparison found differences${NC}"
    exit 1
fi
echo -e "${GREEN}✅ All calculations match Excel${NC}"
echo ""

# Step 5: Generate reports
echo "📄 Step 4: Generating validation reports..."
mkdir -p "$PROJECT_ROOT/reports"

# Run comparison and save results
npx ts-node "$SCRIPT_DIR/compare-excel-calculations.ts" > "$PROJECT_ROOT/reports/comparison-output.txt"

# Check if HTML report was generated
if [ -f "$PROJECT_ROOT/reports/excel-comparison-report.html" ]; then
    echo -e "${GREEN}✅ HTML report generated: reports/excel-comparison-report.html${NC}"
else
    echo -e "${YELLOW}⚠️  HTML report was not generated${NC}"
fi

# Step 6: Summary
echo ""
echo "📈 Validation Summary"
echo "===================="

# Count test results
TOTAL_TESTS=$(grep -c "test" "$PROJECT_ROOT/reports/comparison-output.txt" 2>/dev/null || echo "0")
PASSED_TESTS=$(grep -c "PASS" "$PROJECT_ROOT/reports/comparison-output.txt" 2>/dev/null || echo "0")
FAILED_TESTS=$(grep -c "FAIL" "$PROJECT_ROOT/reports/comparison-output.txt" 2>/dev/null || echo "0")

echo "Total Tests: $TOTAL_TESTS"
echo -e "Passed: ${GREEN}$PASSED_TESTS${NC}"
if [ "$FAILED_TESTS" -gt 0 ]; then
    echo -e "Failed: ${RED}$FAILED_TESTS${NC}"
else
    echo -e "Failed: ${GREEN}0${NC}"
fi

# Calculate success rate
if [ "$TOTAL_TESTS" -gt 0 ]; then
    SUCCESS_RATE=$(( PASSED_TESTS * 100 / TOTAL_TESTS ))
    echo "Success Rate: $SUCCESS_RATE%"
    
    if [ "$SUCCESS_RATE" -eq 100 ]; then
        echo ""
        echo -e "${GREEN}🎉 Perfect match! All calculations align with Excel.${NC}"
        exit 0
    else
        echo ""
        echo -e "${RED}❌ Some calculations don't match Excel. Please review the reports.${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠️  No tests were run${NC}"
    exit 1
fi