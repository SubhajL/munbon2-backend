#!/usr/bin/env ts-node
interface ComparisonResult {
    scenario: string;
    field: string;
    excelValue: number;
    serviceValue: number;
    difference: number;
    percentDiff: number;
    status: 'PASS' | 'FAIL' | 'WARNING';
}
declare function runComparison(): Promise<ComparisonResult[]>;
export { runComparison, ComparisonResult };
//# sourceMappingURL=compare-excel-calculations.d.ts.map