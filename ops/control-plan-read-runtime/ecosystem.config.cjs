const path = require('path');

const runtimeDir = __dirname;
const runtimeEnvDir = process.env.MUNBON_RUNTIME_ENV_DIR || '/etc/munbon/control-plan-read-runtime';

const processFor = (name, wrapper) => ({
  name,
  script: path.join(runtimeDir, wrapper),
  interpreter: '/bin/bash',
  autorestart: true,
  restart_delay: 2000,
  max_restarts: 10,
  env: { MUNBON_RUNTIME_ENV_DIR: runtimeEnvDir },
});

module.exports = {
  apps: [
    processFor('flow-monitoring', 'run-flow.sh'),
    processFor('scheduler', 'run-scheduler.sh'),
    processFor('ros-gis-integration', 'run-ros.sh'),
    processFor('bff-water-planning', 'run-bff.sh'),
  ],
};
