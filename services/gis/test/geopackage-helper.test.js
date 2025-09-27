const { GeoPackageHelper } = require('../src/utils/geopackage-helper');

describe('GeoPackageHelper', () => {
    describe('extractRowData', () => {
        it('should extract properties and geometry from row', () => {
            const row = {
                fid: 1,
                PARCEL_SEQ: '20000000000010717016',
                zone_area: '4',
                area_rai: 4.26,
                plant_id: 'rice',
                start_int: '2024-01-15',
                geom: { type: 'Point', coordinates: [100.5, 13.7] }
            };
            
            const result = GeoPackageHelper.extractRowData(row, 'geom');
            
            expect(result.properties).toEqual({
                fid: 1,
                PARCEL_SEQ: '20000000000010717016',
                zone_area: '4',
                area_rai: 4.26,
                plant_id: 'rice',
                start_int: '2024-01-15'
            });
            expect(result.geometry).toEqual({
                type: 'Point',
                coordinates: [100.5, 13.7]
            });
        });
        
        it('should handle missing geometry column', () => {
            const row = {
                fid: 1,
                PARCEL_SEQ: '20000000000010717016'
            };
            
            const result = GeoPackageHelper.extractRowData(row);
            
            expect(result.properties).toEqual({
                fid: 1,
                PARCEL_SEQ: '20000000000010717016'
            });
            expect(result.geometry).toBeNull();
        });
        
        it('should handle Buffer geometry', () => {
            const row = {
                fid: 1,
                geom: Buffer.from([1, 2, 3, 4])
            };
            
            const result = GeoPackageHelper.extractRowData(row);
            
            expect(result.properties).toEqual({ fid: 1 });
            expect(result.geometry).toEqual({
                type: 'Point',
                coordinates: [0, 0],
                _raw: 'WKB Buffer - needs parsing'
            });
        });
    });
    
    describe('extractAllRows', () => {
        it('should extract all rows using queryForAll', async () => {
            const mockRows = [
                { fid: 1, name: 'Parcel 1', geom: null },
                { fid: 2, name: 'Parcel 2', geom: null }
            ];
            
            const mockFeatureDao = {
                table_name: 'test_table',
                geometryColumn: 'geom',
                queryForAll: jest.fn(() => mockRows)
            };
            
            const result = await GeoPackageHelper.extractAllRows(mockFeatureDao);
            
            expect(result).toHaveLength(2);
            expect(result[0].properties).toEqual({ fid: 1, name: 'Parcel 1' });
            expect(result[1].properties).toEqual({ fid: 2, name: 'Parcel 2' });
            expect(mockFeatureDao.queryForAll).toHaveBeenCalled();
        });
        
        it('should extract all rows using queryForEach', async () => {
            const mockRows = [
                { fid: 1, name: 'Parcel 1' },
                { fid: 2, name: 'Parcel 2' }
            ];
            
            const mockFeatureDao = {
                table_name: 'test_table',
                queryForEach: jest.fn(() => mockRows)
            };
            
            const result = await GeoPackageHelper.extractAllRows(mockFeatureDao);
            
            expect(result).toHaveLength(2);
            expect(mockFeatureDao.queryForEach).toHaveBeenCalled();
        });
        
        it('should handle errors gracefully', async () => {
            const mockFeatureDao = {
                table_name: 'test_table',
                queryForAll: jest.fn(() => { throw new Error('Query failed'); })
            };
            
            const result = await GeoPackageHelper.extractAllRows(mockFeatureDao);
            
            expect(result).toEqual([]);
        });
    });
    
    describe('getTableMetadata', () => {
        it('should extract table metadata', () => {
            const mockFeatureDao = {
                table_name: 'ridplan_data',
                geometryColumn: 'geom',
                columns: {
                    0: { name: 'fid', dataType: 'INTEGER', primaryKey: true },
                    1: { name: 'parcel_seq', dataType: 'TEXT', notNull: true },
                    2: { name: 'area_rai', dataType: 'REAL' }
                },
                srs: {
                    srs_id: 32648,
                    organization: 'EPSG',
                    organization_coordsys_id: 32648
                }
            };
            
            const metadata = GeoPackageHelper.getTableMetadata(mockFeatureDao);
            
            expect(metadata.tableName).toBe('ridplan_data');
            expect(metadata.geometryColumn).toBe('geom');
            expect(metadata.columns).toHaveLength(3);
            expect(metadata.columns[0]).toEqual({
                index: '0',
                name: 'fid',
                type: 'INTEGER',
                isPrimary: true,
                notNull: false
            });
            expect(metadata.srs).toEqual({
                srsId: 32648,
                organization: 'EPSG',
                organizationCoordsysId: 32648
            });
        });
    });
    
    describe('mapToAgriculturalPlot', () => {
        it('should map row data to agricultural plot structure', () => {
            const rowData = {
                properties: {
                    PARCEL_SEQ: '20000000000010717016',
                    FARMER_ID: 'F001',
                    area_rai: 4.26,
                    plant_id: '1',
                    start_int: '2024-01-15',
                    zone_area: '4',
                    wpet: 1200,
                    wprod: 5000,
                    yield_at_mc_kgpr: 450
                },
                geometry: { type: 'Point', coordinates: [100.5, 13.7] }
            };
            
            const result = GeoPackageHelper.mapToAgriculturalPlot(rowData, 'test_table');
            
            expect(result.plot_code).toBe('20000000000010717016');
            expect(result.farmer_id).toBe('F001');
            expect(result.area_hectares).toBeCloseTo(0.6816, 4);
            expect(result.current_crop_type).toBe('rice');
            expect(result.planting_date).toEqual(new Date('2024-01-15'));
            expect(result.properties.ridAttributes.parcelAreaRai).toBe(4.26);
            expect(result.properties.ridAttributes.subMember).toBe('4');
            expect(result.geometry).toEqual({ type: 'Point', coordinates: [100.5, 13.7] });
        });
        
        it('should handle missing values with defaults', () => {
            const rowData = {
                properties: {},
                geometry: null
            };
            
            const result = GeoPackageHelper.mapToAgriculturalPlot(rowData, 'test_table');
            
            expect(result.plot_code).toMatch(/^RID-test_table-\d+$/);
            expect(result.farmer_id).toBeNull();
            expect(result.area_hectares).toBeNull();
            expect(result.current_crop_type).toBeNull();
            expect(result.planting_date).toBeNull();
        });
    });
    
    describe('mapCropType', () => {
        it('should map numeric crop IDs', () => {
            expect(GeoPackageHelper.mapCropType('1')).toBe('rice');
            expect(GeoPackageHelper.mapCropType('2')).toBe('maize');
            expect(GeoPackageHelper.mapCropType('3')).toBe('sugarcane');
            expect(GeoPackageHelper.mapCropType('4')).toBe('cassava');
        });
        
        it('should map text crop types', () => {
            expect(GeoPackageHelper.mapCropType('rice')).toBe('rice');
            expect(GeoPackageHelper.mapCropType('corn')).toBe('maize');
            expect(GeoPackageHelper.mapCropType('SUGARCANE')).toBe('sugarcane');
        });
        
        it('should return original value for unknown types', () => {
            expect(GeoPackageHelper.mapCropType('wheat')).toBe('wheat');
            expect(GeoPackageHelper.mapCropType('5')).toBe('5');
        });
        
        it('should handle null values', () => {
            expect(GeoPackageHelper.mapCropType(null)).toBeNull();
            expect(GeoPackageHelper.mapCropType(undefined)).toBeNull();
        });
    });
    
    describe('parseDate', () => {
        it('should parse valid date strings', () => {
            const date = GeoPackageHelper.parseDate('2024-01-15');
            expect(date).toBeInstanceOf(Date);
            expect(date.toISOString()).toMatch(/2024-01-15/);
        });
        
        it('should handle null values', () => {
            expect(GeoPackageHelper.parseDate(null)).toBeNull();
            expect(GeoPackageHelper.parseDate(undefined)).toBeNull();
            expect(GeoPackageHelper.parseDate('')).toBeNull();
        });
        
        it('should handle invalid date strings', () => {
            expect(GeoPackageHelper.parseDate('invalid-date')).toBeNull();
            expect(GeoPackageHelper.parseDate('12345')).not.toBeNull(); // Unix timestamp
        });
    });
});

// Mock logger to avoid console output during tests
jest.mock('../src/utils/logger', () => ({
    logger: {
        info: jest.fn(),
        debug: jest.fn(),
        error: jest.fn(),
        warn: jest.fn()
    }
}));