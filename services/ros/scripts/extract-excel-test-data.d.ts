#!/usr/bin/env ts-node
interface ExtractedTestCase {
    description: string;
    input: {
        cropType: string;
        cropWeek: number;
        calendarWeek: number;
        calendarMonth: number;
        areaRai: number;
    };
    excelCalculation: {
        monthlyETo: number;
        weeklyETo: number;
        kcValue: number;
        percolation: number;
        cropWaterDemandMm: number;
        cropWaterDemandM3: number;
        formula: {
            etoCalc: string;
            kcLookup: string;
            demandCalc: string;
            volumeCalc: string;
        };
    };
}
declare function extractTestDataFromExcel(excelPath: string): ExtractedTestCase[];
export { extractTestDataFromExcel };
//# sourceMappingURL=extract-excel-test-data.d.ts.map