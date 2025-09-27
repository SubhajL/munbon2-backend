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

async function listTables() {
    try {
        await sql.connect(config);
        console.log('✅ Connected to MSSQL successfully!');
        
        // List all tables
        const tables = await sql.query`
            SELECT TABLE_SCHEMA, TABLE_NAME 
            FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_TYPE = 'BASE TABLE'
            ORDER BY TABLE_SCHEMA, TABLE_NAME`;
        
        console.log('\n📋 Tables in database:');
        tables.recordset.forEach(table => {
            console.log(`  - ${table.TABLE_SCHEMA}.${table.TABLE_NAME}`);
        });
        
        // Look for AOS-related tables
        const aosTables = await sql.query`
            SELECT TABLE_SCHEMA, TABLE_NAME 
            FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_NAME LIKE '%aos%' OR TABLE_NAME LIKE '%AOS%' OR TABLE_NAME LIKE '%weather%'`;
        
        if (aosTables.recordset.length > 0) {
            console.log('\n🌤️ AOS/Weather related tables:');
            aosTables.recordset.forEach(table => {
                console.log(`  - ${table.TABLE_SCHEMA}.${table.TABLE_NAME}`);
            });
        }
        
        await sql.close();
    } catch (err) {
        console.error('❌ Error:', err.message);
    }
}

listTables();