const sql = require('mssql');

const config = {
    server: 'moonup.hopto.org',
    port: 1433,
    user: 'sa',
    password: 'bangkok1234',
    database: 'db_scada',
    options: {
        encrypt: true,
        trustServerCertificate: true,
        enableArithAbort: true
    }
};

async function checkAOSStructure() {
    try {
        await sql.connect(config);
        console.log('✅ Connected to MSSQL successfully!');
        
        // Get table columns
        const columns = await sql.query`
            SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'tb_aos'
            ORDER BY ORDINAL_POSITION`;
        
        console.log('\n📋 Columns in tb_aos table:');
        columns.recordset.forEach(col => {
            console.log(`  - ${col.COLUMN_NAME} (${col.DATA_TYPE})`);
        });
        
        // Get a sample record
        const sample = await sql.query`SELECT TOP 1 * FROM tb_aos`;
        
        if (sample.recordset.length > 0) {
            console.log('\n📊 Sample record:');
            console.log(sample.recordset[0]);
        }
        
        await sql.close();
    } catch (err) {
        console.error('❌ Error:', err.message);
    }
}

checkAOSStructure();