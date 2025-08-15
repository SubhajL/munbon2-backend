/**
 * Debug Bootstrap - Automatically injected into all services
 * Provides comprehensive request/response logging and debugging
 */

const morgan = require('morgan');
const chalk = require('chalk');
const util = require('util');

// Enhanced console logging with colors
const originalLog = console.log;
const originalError = console.error;
const originalWarn = console.warn;

console.log = (...args) => {
  const timestamp = new Date().toISOString();
  originalLog(chalk.gray(`[${timestamp}]`), chalk.green('[LOG]'), ...args);
};

console.error = (...args) => {
  const timestamp = new Date().toISOString();
  originalError(chalk.gray(`[${timestamp}]`), chalk.red('[ERROR]'), ...args);
};

console.warn = (...args) => {
  const timestamp = new Date().toISOString();
  originalWarn(chalk.gray(`[${timestamp}]`), chalk.yellow('[WARN]'), ...args);
};

console.debug = (...args) => {
  const timestamp = new Date().toISOString();
  originalLog(chalk.gray(`[${timestamp}]`), chalk.cyan('[DEBUG]'), ...args);
};

// Global error handlers
process.on('uncaughtException', (error) => {
  console.error('🔥 Uncaught Exception:', error);
  console.error('Stack:', error.stack);
});

process.on('unhandledRejection', (reason, promise) => {
  console.error('🔥 Unhandled Rejection at:', promise, 'reason:', reason);
});

// Request ID generator
let requestCounter = 0;
global.generateRequestId = () => {
  requestCounter++;
  return `${process.env.HOSTNAME || 'debug'}-${Date.now()}-${requestCounter}`;
};

// Request/Response logger middleware
global.debugLogger = (req, res, next) => {
  const requestId = global.generateRequestId();
  req.requestId = requestId;
  
  const startTime = Date.now();
  const originalSend = res.send;
  const originalJson = res.json;
  
  // Log request
  console.log(chalk.blue('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'));
  console.log(chalk.blue('➤ REQUEST'), chalk.yellow(`[${requestId}]`));
  console.log(chalk.gray('Time:'), new Date().toISOString());
  console.log(chalk.gray('Method:'), chalk.green(req.method));
  console.log(chalk.gray('URL:'), req.originalUrl);
  console.log(chalk.gray('Headers:'), JSON.stringify(req.headers, null, 2));
  if (req.body && Object.keys(req.body).length > 0) {
    console.log(chalk.gray('Body:'), JSON.stringify(req.body, null, 2));
  }
  if (req.query && Object.keys(req.query).length > 0) {
    console.log(chalk.gray('Query:'), JSON.stringify(req.query, null, 2));
  }
  
  // Intercept response
  res.send = function(data) {
    res.responseData = data;
    logResponse();
    originalSend.call(this, data);
  };
  
  res.json = function(data) {
    res.responseData = data;
    logResponse();
    originalJson.call(this, data);
  };
  
  const logResponse = () => {
    const duration = Date.now() - startTime;
    console.log(chalk.green('✓ RESPONSE'), chalk.yellow(`[${requestId}]`));
    console.log(chalk.gray('Status:'), res.statusCode >= 400 ? chalk.red(res.statusCode) : chalk.green(res.statusCode));
    console.log(chalk.gray('Duration:'), chalk.cyan(`${duration}ms`));
    if (res.responseData) {
      const dataStr = typeof res.responseData === 'string' 
        ? res.responseData 
        : JSON.stringify(res.responseData, null, 2);
      console.log(chalk.gray('Response:'), dataStr.substring(0, 1000));
      if (dataStr.length > 1000) {
        console.log(chalk.gray(`... ${dataStr.length - 1000} more characters`));
      }
    }
    console.log(chalk.blue('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'));
  };
  
  next();
};

// SQL Query logger
if (process.env.ENABLE_SQL_LOGGING === 'true') {
  const originalQuery = require('pg').Client.prototype.query;
  require('pg').Client.prototype.query = function(...args) {
    const query = args[0];
    const params = args[1];
    console.debug(chalk.magenta('SQL:'), typeof query === 'string' ? query : query.text);
    if (params) {
      console.debug(chalk.magenta('Params:'), params);
    }
    return originalQuery.apply(this, args);
  };
}

// Axios request/response logger
if (typeof require('axios') !== 'undefined') {
  const axios = require('axios');
  
  axios.interceptors.request.use(request => {
    console.debug(chalk.cyan('📤 Outgoing HTTP:'), request.method?.toUpperCase(), request.url);
    if (request.data) {
      console.debug(chalk.cyan('Request Data:'), request.data);
    }
    return request;
  });
  
  axios.interceptors.response.use(
    response => {
      console.debug(chalk.green('📥 HTTP Response:'), response.status, response.config.url);
      return response;
    },
    error => {
      console.error(chalk.red('📥 HTTP Error:'), error.response?.status, error.config?.url);
      console.error(chalk.red('Error Details:'), error.response?.data);
      return Promise.reject(error);
    }
  );
}

// Memory usage logger
setInterval(() => {
  const usage = process.memoryUsage();
  console.debug(chalk.gray('Memory:'), {
    rss: `${Math.round(usage.rss / 1024 / 1024)}MB`,
    heap: `${Math.round(usage.heapUsed / 1024 / 1024)}/${Math.round(usage.heapTotal / 1024 / 1024)}MB`,
    external: `${Math.round(usage.external / 1024 / 1024)}MB`
  });
}, 30000);

console.log(chalk.green('✨ Debug Bootstrap Loaded Successfully'));
console.log(chalk.gray('Service:'), process.env.HOSTNAME || 'unknown');
console.log(chalk.gray('Port:'), process.env.PORT || 'unknown');
console.log(chalk.gray('Node Version:'), process.version);
console.log(chalk.gray('Debug Mode:'), chalk.green('ENABLED'));

module.exports = {
  debugLogger
};