const { Client } = require('pg');

async function testEC2Connection() {
    const configs = [
        { 
            name: 'Config from .env.local',
            host: process.env.EC2_HOST || '43.208.201.191',
            port: 5432,
            database: 'sensor_data',
            user: 'postgres',
            password: 'P@ssw0rd123!'
        },
        {
            name: 'Alternative password',
            host: process.env.EC2_HOST || '43.208.201.191',
            port: 5432,
            database: 'sensor_data',
            user: 'postgres',
            password: 'postgres123'
        }
    ];

    for (const config of configs) {
        console.log(`\nTesting ${config.name}...`);
        const client = new Client(config);
        
        try {
            await client.connect();
            console.log('✅ Connection successful!');
            
            const result = await client.query('SELECT version()');
            console.log('PostgreSQL version:', result.rows[0].version);
            
            const tables = await client.query(`
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                ORDER BY table_name
            `);
            console.log('Tables:', tables.rows.map(r => r.table_name).join(', '));
            
            await client.end();
            return true;
        } catch (error) {
            console.log('❌ Connection failed:', error.message);
            await client.end().catch(() => {});
        }
    }
    
    return false;
}

testEC2Connection().then(success => {
    if (!success) {
        console.log('\n❌ All connection attempts failed');
        process.exit(1);
    }
});