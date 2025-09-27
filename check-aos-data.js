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

async function checkAOSData() {
    try {
        await sql.connect(config);
        console.log('✅ Connected to MSSQL successfully!');
        
        // Get latest records
        const latest = await sql.query`
            SELECT TOP 10 * FROM tb_aos 
            ORDER BY date_time DESC`;
        
        console.log(`\n📊 Found ${latest.recordset.length} latest AOS records:`);
        
        if (latest.recordset.length > 0) {
            console.log('\nLatest record:');
            console.log(latest.recordset[0]);
            
            console.log('\nDate range:');
            console.log('Latest:', latest.recordset[0].date_time);
            console.log('10th record:', latest.recordset[latest.recordset.length - 1].date_time);
        }
        
        // Count total records
        const count = await sql.query`SELECT COUNT(*) as total FROM tb_aos`;
        console.log(`\nTotal AOS records: ${count.recordset[0].total}`);
        
        // Get date range
        const dateRange = await sql.query`
            SELECT 
                MIN(date_time) as earliest,
                MAX(date_time) as latest
            FROM tb_aos`;
        
        console.log('\nData date range:');
        console.log('Earliest:', dateRange.recordset[0].earliest);
        console.log('Latest:', dateRange.recordset[0].latest);
        
        await sql.close();
    } catch (err) {
        console.error('❌ Error:', err.message);
        console.error('Full error:', err);
    }
}

checkAOSData();