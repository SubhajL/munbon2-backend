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

async function checkLatestAOS() {
    try {
        await sql.connect(config);
        console.log('✅ Connected to MSSQL successfully!');
        
        // Get latest records
        const latest = await sql.query`
            SELECT TOP 10 * FROM tb_aos 
            ORDER BY data_datetime DESC`;
        
        console.log(`\n📊 Latest AOS records:`);
        latest.recordset.forEach((record, idx) => {
            console.log(`${idx + 1}. ${record.data_datetime} - Temp: ${record.temp}°C, Rain: ${record.raingauge}mm, Wind: ${record.windspeed}m/s`);
        });
        
        // Get date range
        const dateRange = await sql.query`
            SELECT 
                MIN(data_datetime) as earliest,
                MAX(data_datetime) as latest,
                COUNT(*) as total
            FROM tb_aos`;
        
        console.log('\n📅 Data summary:');
        console.log('Total records:', dateRange.recordset[0].total);
        console.log('Earliest:', dateRange.recordset[0].earliest);
        console.log('Latest:', dateRange.recordset[0].latest);
        
        // Check records from 2025
        const recent2025 = await sql.query`
            SELECT COUNT(*) as count_2025 
            FROM tb_aos 
            WHERE data_datetime >= '2025-01-01'`;
        
        console.log('\nRecords from 2025:', recent2025.recordset[0].count_2025);
        
        // Check last few months
        const lastMonths = await sql.query`
            SELECT 
                YEAR(data_datetime) as year,
                MONTH(data_datetime) as month,
                COUNT(*) as record_count
            FROM tb_aos
            WHERE data_datetime >= '2025-01-01'
            GROUP BY YEAR(data_datetime), MONTH(data_datetime)
            ORDER BY year DESC, month DESC`;
        
        console.log('\n📊 Monthly record counts (2025):');
        lastMonths.recordset.forEach(m => {
            console.log(`  ${m.year}-${String(m.month).padStart(2, '0')}: ${m.record_count} records`);
        });
        
        await sql.close();
    } catch (err) {
        console.error('❌ Error:', err.message);
    }
}

checkLatestAOS();