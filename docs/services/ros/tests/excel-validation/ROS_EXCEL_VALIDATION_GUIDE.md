# ROS Excel Validation Testing Guide

## Overview
This guide describes how to validate that the ROS service calculations match exactly with the original ROS Excel worksheet calculations.

## Testing Strategy

### 1. Create Test Data from Excel

#### Step 1: Export Excel Test Cases
Create a test dataset by extracting specific scenarios from the Excel worksheet:

```typescript
// test-cases-from-excel.json
{
  "testCases": [
    {
      "testId": "TC001",
      "description": "Rice Week 5 in May",
      "input": {
        "cropType": "rice",
        "cropWeek": 5,
        "calendarMonth": 5,
        "calendarWeek": 18,
        "areaRai": 100,
        "aosStation": "นครราชสีมา"
      },
      "excelCalculation": {
        "monthlyETo": 148.8,
        "weeklyETo": 37.2,
        "kcValue": 1.10,
        "percolation": 14,
        "cropWaterDemandMm": 54.92,
        "cropWaterDemandM3": 8787.2
      }
    },
    {
      "testId": "TC002",
      "description": "Corn Week 10 in July",
      "input": {
        "cropType": "corn",
        "cropWeek": 10,
        "calendarMonth": 7,
        "calendarWeek": 28,
        "areaRai": 50,
        "aosStation": "นครราชสีมา"
      },
      "excelCalculation": {
        "monthlyETo": 130.2,
        "weeklyETo": 32.55,
        "kcValue": 1.20,
        "percolation": 14,
        "cropWaterDemandMm": 53.06,
        "cropWaterDemandM3": 4244.8
      }
    }
  ]
}
```

### 2. Unit Test Implementation

```typescript
// tests/unit/water-demand-excel-validation.test.ts
import { waterDemandService } from '@services/water-demand.service';
import testCases from './test-cases-from-excel.json';

describe('ROS Excel Validation Tests', () => {
  testCases.testCases.forEach((testCase) => {
    describe(`Test Case ${testCase.testId}: ${testCase.description}`, () => {
      let result: any;

      beforeAll(async () => {
        // Calculate using our service
        result = await waterDemandService.calculateWaterDemand({
          areaId: 'TEST-PLOT',
          areaType: 'plot',
          areaRai: testCase.input.areaRai,
          cropType: testCase.input.cropType,
          cropWeek: testCase.input.cropWeek,
          calendarWeek: testCase.input.calendarWeek,
          calendarYear: 2024
        });
      });

      test('Monthly ETo should match Excel', () => {
        expect(result.monthlyETo).toBe(testCase.excelCalculation.monthlyETo);
      });

      test('Weekly ETo should match Excel', () => {
        expect(result.weeklyETo).toBeCloseTo(
          testCase.excelCalculation.weeklyETo, 
          2
        );
      });

      test('Kc value should match Excel', () => {
        expect(result.kcValue).toBe(testCase.excelCalculation.kcValue);
      });

      test('Water demand in mm should match Excel', () => {
        expect(result.cropWaterDemandMm).toBeCloseTo(
          testCase.excelCalculation.cropWaterDemandMm, 
          2
        );
      });

      test('Water demand in m³ should match Excel', () => {
        expect(result.cropWaterDemandM3).toBeCloseTo(
          testCase.excelCalculation.cropWaterDemandM3, 
          1
        );
      });

      test('Calculation formula verification', () => {
        // Verify the formula: (ETo × Kc) + Percolation
        const expectedDemandMm = 
          (result.weeklyETo * result.kcValue) + result.percolation;
        expect(result.cropWaterDemandMm).toBeCloseTo(expectedDemandMm, 2);

        // Verify m³ conversion: mm × area × 1.6
        const expectedDemandM3 = 
          result.cropWaterDemandMm * testCase.input.areaRai * 1.6;
        expect(result.cropWaterDemandM3).toBeCloseTo(expectedDemandM3, 1);
      });
    });
  });
});
```

### 3. Excel Formula Extraction Script

```typescript
// scripts/extract-excel-formulas.ts
import XLSX from 'xlsx';

interface ExcelFormula {
  cell: string;
  formula: string;
  value: any;
}

export function extractExcelFormulas(filePath: string): ExcelFormula[] {
  const workbook = XLSX.readFile(filePath);
  const formulas: ExcelFormula[] = [];

  // Extract from ETo worksheet
  const etoSheet = workbook.Sheets['ETo'];
  for (const cell in etoSheet) {
    if (etoSheet[cell].f) { // Has formula
      formulas.push({
        cell: cell,
        formula: etoSheet[cell].f,
        value: etoSheet[cell].v
      });
    }
  }

  // Extract from Kc worksheet
  const kcSheet = workbook.Sheets['Kc'];
  // ... similar extraction

  return formulas;
}

// Usage
const formulas = extractExcelFormulas('ROS_Calculation.xlsx');
console.log('Excel formulas:', formulas);
```

### 4. Integration Test with Excel Comparison

```typescript
// tests/integration/excel-comparison.test.ts
import XLSX from 'xlsx';
import { waterDemandService } from '@services/water-demand.service';

describe('Excel vs Service Comparison', () => {
  let excelWorkbook: XLSX.WorkBook;
  
  beforeAll(() => {
    excelWorkbook = XLSX.readFile('tests/fixtures/ROS_Calculation.xlsx');
  });

  test('Compare full season calculation with Excel', async () => {
    // Get Excel calculation for rice full season
    const calculationSheet = excelWorkbook.Sheets['Calculation'];
    
    // Extract all weekly values from Excel
    const excelWeeklyValues = [];
    for (let week = 1; week <= 16; week++) {
      const rowNum = week + 10; // Assuming data starts at row 11
      excelWeeklyValues.push({
        week: week,
        eto: calculationSheet[`C${rowNum}`].v,
        kc: calculationSheet[`D${rowNum}`].v,
        demandMm: calculationSheet[`E${rowNum}`].v,
        demandM3: calculationSheet[`F${rowNum}`].v
      });
    }

    // Calculate using service
    const serviceResult = await waterDemandService.calculateSeasonalWaterDemand(
      'TEST-PLOT',
      'plot',
      1000, // 1000 rai
      'rice',
      new Date('2024-05-01'),
      false
    );

    // Compare each week
    serviceResult.weeklyDetails.forEach((weekDetail, index) => {
      const excelWeek = excelWeeklyValues[index];
      expect(weekDetail.cropWaterDemandMm).toBeCloseTo(
        excelWeek.demandMm, 
        2
      );
      expect(weekDetail.cropWaterDemandM3).toBeCloseTo(
        excelWeek.demandM3, 
        0
      );
    });

    // Compare totals
    const excelTotal = calculationSheet['F28'].v; // Total cell
    expect(serviceResult.totalWaterDemandM3).toBeCloseTo(excelTotal, 0);
  });
});
```

### 5. Visual Comparison Tool

```typescript
// scripts/excel-service-comparison-tool.ts
import chalk from 'chalk';
import Table from 'cli-table3';

interface ComparisonResult {
  field: string;
  excelValue: number;
  serviceValue: number;
  difference: number;
  percentDiff: number;
  status: 'PASS' | 'FAIL';
}

export async function compareWithExcel(
  testCase: any
): Promise<ComparisonResult[]> {
  const results: ComparisonResult[] = [];
  
  // Run service calculation
  const serviceResult = await waterDemandService.calculateWaterDemand(
    testCase.input
  );
  
  // Compare each field
  const fieldsToCompare = [
    'monthlyETo', 'weeklyETo', 'kcValue', 
    'cropWaterDemandMm', 'cropWaterDemandM3'
  ];
  
  fieldsToCompare.forEach(field => {
    const excelVal = testCase.excelCalculation[field];
    const serviceVal = serviceResult[field];
    const diff = Math.abs(excelVal - serviceVal);
    const percentDiff = (diff / excelVal) * 100;
    
    results.push({
      field,
      excelValue: excelVal,
      serviceValue: serviceVal,
      difference: diff,
      percentDiff,
      status: percentDiff < 0.01 ? 'PASS' : 'FAIL'
    });
  });
  
  return results;
}

// Display results in table
export function displayComparisonResults(results: ComparisonResult[]) {
  const table = new Table({
    head: ['Field', 'Excel', 'Service', 'Diff', '%', 'Status'],
    colWidths: [20, 15, 15, 10, 10, 10]
  });
  
  results.forEach(r => {
    table.push([
      r.field,
      r.excelValue.toFixed(2),
      r.serviceValue.toFixed(2),
      r.difference.toFixed(4),
      r.percentDiff.toFixed(2) + '%',
      r.status === 'PASS' 
        ? chalk.green(r.status) 
        : chalk.red(r.status)
    ]);
  });
  
  console.log(table.toString());
}
```

### 6. Automated Excel Test Generator

```typescript
// scripts/generate-excel-tests.ts
import XLSX from 'xlsx';

export function generateTestsFromExcel(excelPath: string) {
  const workbook = XLSX.readFile(excelPath);
  const tests = [];
  
  // Read test scenarios from Excel
  const testSheet = workbook.Sheets['TestScenarios'];
  const scenarios = XLSX.utils.sheet_to_json(testSheet);
  
  scenarios.forEach(scenario => {
    // For each scenario, calculate expected values
    const monthlyETo = getEToValue(workbook, scenario.month);
    const kcValue = getKcValue(workbook, scenario.cropType, scenario.week);
    const weeklyETo = monthlyETo / 4;
    const demandMm = (weeklyETo * kcValue) + 14;
    const demandM3 = demandMm * scenario.areaRai * 1.6;
    
    tests.push({
      input: scenario,
      expected: {
        monthlyETo,
        weeklyETo,
        kcValue,
        cropWaterDemandMm: demandMm,
        cropWaterDemandM3: demandM3
      }
    });
  });
  
  // Write tests to file
  fs.writeFileSync(
    'tests/generated/excel-tests.json',
    JSON.stringify(tests, null, 2)
  );
}
```

### 7. Continuous Validation Script

```bash
#!/bin/bash
# scripts/validate-against-excel.sh

echo "Running ROS Excel Validation Tests..."

# 1. Extract latest data from Excel
npm run extract-excel-data

# 2. Run unit tests
npm run test:excel-validation

# 3. Run integration tests
npm run test:excel-integration

# 4. Generate comparison report
npm run compare-excel-output

# 5. Check for differences
if [ $? -eq 0 ]; then
  echo "✅ All calculations match Excel!"
else
  echo "❌ Differences found - see report above"
  exit 1
fi
```

### 8. Edge Case Testing

```typescript
// tests/edge-cases/excel-edge-cases.test.ts
describe('Excel Edge Cases', () => {
  test('Week spanning two months', async () => {
    // Test calculation when week starts in one month and ends in another
    const result = await waterDemandService.calculateWaterDemand({
      areaId: 'TEST',
      cropType: 'rice',
      cropWeek: 8,
      calendarWeek: 5, // Early February - spans Jan/Feb
      calendarYear: 2024,
      areaRai: 100
    });
    
    // Should use February ETo according to Excel logic
    expect(result.monthlyETo).toBe(122.4); // February value
  });
  
  test('Decimal precision matching', async () => {
    // Excel uses specific decimal precision
    const result = await calculateWithExcelPrecision(
      37.2,  // ETo
      1.105, // Kc with 3 decimals
      14     // Percolation
    );
    
    // Match Excel's rounding behavior
    expect(result).toBe(55.106); // Not 55.11
  });
});
```

### 9. NPM Scripts for Testing

```json
// package.json
{
  "scripts": {
    "test:excel-validation": "jest tests/unit/water-demand-excel-validation.test.ts",
    "test:excel-integration": "jest tests/integration/excel-comparison.test.ts",
    "extract-excel-data": "ts-node scripts/extract-excel-formulas.ts",
    "compare-excel-output": "ts-node scripts/excel-service-comparison-tool.ts",
    "generate-excel-tests": "ts-node scripts/generate-excel-tests.ts",
    "validate-excel": "bash scripts/validate-against-excel.sh"
  }
}
```

### 10. Test Data Maintenance

```typescript
// tests/fixtures/excel-test-data.ts
export const EXCEL_TEST_DATA = {
  // Exact values from Excel for validation
  ETO_MONTHLY: {
    'นครราชสีมา': {
      1: 108.5, 2: 122.4, 3: 151.9, 4: 156.0,
      5: 148.8, 6: 132.0, 7: 130.2, 8: 127.1,
      9: 114.0, 10: 108.5, 11: 102.0, 12: 99.2
    }
  },
  
  KC_WEEKLY: {
    rice: {
      1: 1.05, 2: 1.05, 3: 1.05, 4: 1.05,
      5: 1.10, 6: 1.15, 7: 1.20, 8: 1.20,
      // ... all 16 weeks
    },
    corn: {
      // ... all weeks
    }
  },
  
  // Known Excel calculation results for regression testing
  KNOWN_CALCULATIONS: [
    {
      scenario: 'Rice Week 5, May, 100 rai',
      input: { /* ... */ },
      excelOutput: { /* exact Excel values */ }
    }
  ]
};
```

## Running the Validation

```bash
# Full validation suite
npm run validate-excel

# Quick check for specific test case
npm run test:excel-validation -- --testNamePattern="Rice Week 5"

# Generate new test cases from updated Excel
npm run generate-excel-tests -- --excel-file=./new-ROS.xlsx

# Visual comparison report
npm run compare-excel-output -- --format=html > comparison-report.html
```

## Success Criteria

The ROS service calculation is considered valid when:
1. All ETo values match Excel exactly
2. All Kc values match Excel exactly  
3. Water demand calculations match within 0.01% tolerance
4. Edge cases (month boundaries, decimal precision) match Excel behavior
5. Full season calculations match Excel totals