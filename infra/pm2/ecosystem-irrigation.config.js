const { getIrrigationProcesses } = require('./dist/build-irrigation-config');

module.exports = {
  apps: getIrrigationProcesses(),
};
