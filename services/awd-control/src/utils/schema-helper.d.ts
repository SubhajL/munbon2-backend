export declare class SchemaHelper {
    private postgresSchema;
    private timescaleSchema;
    private gisSchema;
    constructor();
    prefixTable(tableName: string, schemaType?: 'postgres' | 'timescale' | 'gis'): string;
    getTableName(originalTable: string): string;
    convertQuery(query: string): string;
    getSearchPath(schemaType?: 'postgres' | 'timescale'): string;
}
export declare const schemaHelper: SchemaHelper;
//# sourceMappingURL=schema-helper.d.ts.map