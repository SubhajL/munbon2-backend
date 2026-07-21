const { getScadaFieldProcesses } = require('./dist/build-scada-field-config');

module.exports = {
  apps: getScadaFieldProcesses(),
};
