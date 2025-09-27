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

async function testConnection() {
    try {
        console.log('Connecting to MSSQL with config:', {
            ...config,
            password: '***hidden***'
        });
        
        await sql.connect(config);
        console.log('✅ Connected to MSSQL successfully!');
        
        // Test query
        const result = await sql.query`SELECT TOP 5 * FROM tbl_data_aos ORDER BY data_datetime DESC`;
        console.log(`✅ Found ${result.recordset.length} AOS records`);
        
        if (result.recordset.length > 0) {
            console.log('Latest record:', result.recordset[0]);
        }
        
        await sql.close();
    } catch (err) {
        console.error('❌ MSSQL connection error:', err.message);
        console.error('Full error:', err);
    }
}

testConnection();