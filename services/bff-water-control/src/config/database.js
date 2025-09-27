const sql = require('mssql');
const winston = require('winston');

const logger = winston.createLogger({
  level: 'info',
  format: winston.format.json(),
  transports: [
    new winston.transports.Console({
      format: winston.format.simple()
    })
  ]
});

// SCADA Database configuration
const scadaConfig = {
  server: process.env.SCADA_DB_HOST,
  port: parseInt(process.env.SCADA_DB_PORT),
  database: process.env.SCADA_DB_NAME,
  user: process.env.SCADA_DB_USER,
  password: process.env.SCADA_DB_PASSWORD,
  options: {
    encrypt: process.env.SCADA_DB_ENCRYPT === 'true',
    trustServerCertificate: process.env.SCADA_DB_TRUST_SERVER_CERT === 'true',
    enableArithAbort: true
  },
  pool: {
    max: 10,
    min: 0,
    idleTimeoutMillis: 30000
  }
};

let scadaPool = null;

/**
 * Initialize SCADA database connection pool
 */
async function initializeScadaConnection() {
  try {
    if (!scadaPool) {
      scadaPool = await sql.connect(scadaConfig);
      logger.info('SCADA database connection established');
      
      // Test the connection
      const result = await scadaPool.query`SELECT 1 as test`;
      logger.info('SCADA database connection test successful');
    }
    return scadaPool;
  } catch (error) {
    logger.error('Failed to connect to SCADA database:', error);
    throw error;
  }
}

/**
 * Write gate command to SCADA database
 * @param {Object} command - Gate command object
 * @param {string} command.gateName - Gate alias name
 * @param {number} command.gateLevel - Target gate level in cm
 * @param {Date} command.startDateTime - When to execute the command
 * @returns {Promise<Object>} - Result of the database operation
 */
async function writeGateCommand(command) {
  try {
    const pool = await initializeScadaConnection();
    const request = pool.request();
    
    // Input parameters
    request.input('gate_name', sql.NVarChar(50), command.gateName);
    request.input('gate_level', sql.Float, command.gateLevel);
    request.input('startdatetime', sql.DateTime, command.startDateTime);
    request.input('completestatus', sql.Int, 0); // 0 = pending
    
    // Insert command
    const result = await request.query`
      INSERT INTO tb_gatelevel_command 
      (gate_name, gate_level, startdatetime, completestatus)
      VALUES (@gate_name, @gate_level, @startdatetime, @completestatus);
      
      SELECT SCOPE_IDENTITY() as id;
    `;
    
    const commandId = result.recordset[0].id;
    logger.info(`Gate command written to SCADA: ID=${commandId}, Gate=${command.gateName}, Level=${command.gateLevel}cm`);
    
    return {
      success: true,
      commandId,
      ...command
    };
  } catch (error) {
    logger.error('Failed to write gate command:', error);
    throw error;
  }
}

/**
 * Check command completion status
 * @param {number} commandId - Command ID to check
 * @returns {Promise<Object>} - Command status
 */
async function checkCommandStatus(commandId) {
  try {
    const pool = await initializeScadaConnection();
    const request = pool.request();
    
    request.input('id', sql.Int, commandId);
    
    const result = await request.query`
      SELECT id, gate_name, gate_level, startdatetime, completestatus
      FROM tb_gatelevel_command
      WHERE id = @id
    `;
    
    if (result.recordset.length === 0) {
      throw new Error(`Command ID ${commandId} not found`);
    }
    
    const command = result.recordset[0];
    return {
      id: command.id,
      gateName: command.gate_name,
      gateLevel: command.gate_level,
      startDateTime: command.startdatetime,
      completed: command.completestatus === 1,
      status: command.completestatus === 1 ? 'completed' : 'pending'
    };
  } catch (error) {
    logger.error('Failed to check command status:', error);
    throw error;
  }
}

/**
 * Get recent gate commands
 * @param {number} hours - Number of hours to look back
 * @returns {Promise<Array>} - Array of recent commands
 */
async function getRecentCommands(hours = 24) {
  try {
    const pool = await initializeScadaConnection();
    const request = pool.request();
    
    const since = new Date();
    since.setHours(since.getHours() - hours);
    
    request.input('since', sql.DateTime, since);
    
    const result = await request.query`
      SELECT id, gate_name, gate_level, startdatetime, completestatus
      FROM tb_gatelevel_command
      WHERE startdatetime >= @since
      ORDER BY startdatetime DESC
    `;
    
    return result.recordset.map(cmd => ({
      id: cmd.id,
      gateName: cmd.gate_name,
      gateLevel: cmd.gate_level,
      startDateTime: cmd.startdatetime,
      completed: cmd.completestatus === 1,
      status: cmd.completestatus === 1 ? 'completed' : 'pending'
    }));
  } catch (error) {
    logger.error('Failed to get recent commands:', error);
    throw error;
  }
}

/**
 * Close database connections
 */
async function closeConnections() {
  try {
    if (scadaPool) {
      await scadaPool.close();
      logger.info('SCADA database connection closed');
    }
  } catch (error) {
    logger.error('Error closing database connections:', error);
  }
}

module.exports = {
  initializeScadaConnection,
  writeGateCommand,
  checkCommandStatus,
  getRecentCommands,
  closeConnections
};