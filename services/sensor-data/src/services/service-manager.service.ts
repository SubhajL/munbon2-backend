import pm2 from 'pm2';
import type { Proc } from 'pm2';

export interface ServiceStatus {
  name: string;
  status: string;
  uptimeMs: number;
  uptimeFormatted: string;
  cpu: number;
  memory: number;
  restartCount: number;
  createdAt: number;
}

const PM2_TIMEOUT_MS = 3000;

function connectPM2(): Promise<void> {
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => {
      reject(new Error('PM2 connection timeout'));
    }, PM2_TIMEOUT_MS);

    pm2.connect((err) => {
      clearTimeout(timeout);
      if (err) {
        reject(err);
      } else {
        resolve();
      }
    });
  });
}

function listProcesses(): Promise<Proc[]> {
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => {
      reject(new Error('PM2 list timeout'));
    }, PM2_TIMEOUT_MS);

    pm2.list((err, list) => {
      clearTimeout(timeout);
      if (err) {
        reject(err);
      } else {
        resolve(list);
      }
    });
  });
}

function describeProcess(name: string): Promise<Proc[]> {
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => {
      reject(new Error('PM2 describe timeout'));
    }, PM2_TIMEOUT_MS);

    pm2.describe(name, (err, processDescription) => {
      clearTimeout(timeout);
      if (err) {
        reject(err);
      } else {
        resolve(processDescription);
      }
    });
  });
}

function startProcess(name: string): Promise<Proc> {
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => {
      reject(new Error('PM2 start timeout'));
    }, PM2_TIMEOUT_MS);

    pm2.start(name, (err, proc) => {
      clearTimeout(timeout);
      if (err) {
        reject(err);
      } else {
        resolve(proc);
      }
    });
  });
}

function stopProcess(name: string): Promise<Proc> {
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => {
      reject(new Error('PM2 stop timeout'));
    }, PM2_TIMEOUT_MS);

    pm2.stop(name, (err, proc) => {
      clearTimeout(timeout);
      if (err) {
        reject(err);
      } else {
        resolve(proc);
      }
    });
  });
}

export function calculateUptime(startTimeMs: number): string {
  if (startTimeMs === 0) {
    return '0d 0h 0m';
  }

  const uptimeMs = Date.now() - startTimeMs;
  const days = Math.floor(uptimeMs / (24 * 60 * 60 * 1000));
  const hours = Math.floor((uptimeMs % (24 * 60 * 60 * 1000)) / (60 * 60 * 1000));
  const minutes = Math.floor((uptimeMs % (60 * 60 * 1000)) / (60 * 1000));

  return `${days}d ${hours}h ${minutes}m`;
}

function mapProcessToStatus(proc: Proc): ServiceStatus {
  const pm2Env = (proc as any).pm2_env;
  const monit = (proc as any).monit;
  const status = pm2Env?.status || 'unknown';
  const uptimeMs = status === 'online' && pm2Env?.pm_uptime 
    ? Date.now() - pm2Env.pm_uptime 
    : 0;

  return {
    name: proc.name || 'unknown',
    status,
    uptimeMs,
    uptimeFormatted: calculateUptime(pm2Env?.pm_uptime || 0),
    cpu: monit?.cpu || 0,
    memory: monit?.memory || 0,
    restartCount: pm2Env?.restart_time || 0,
    createdAt: pm2Env?.created_at || 0
  };
}

export async function getServicesList(): Promise<ServiceStatus[]> {
  await connectPM2();
  
  try {
    const processes = await listProcesses();
    return processes.map(mapProcessToStatus);
  } finally {
    pm2.disconnect();
  }
}

export async function getServiceStatus(serviceName: string): Promise<ServiceStatus> {
  await connectPM2();
  
  try {
    const processes = await describeProcess(serviceName);
    
    if (processes.length === 0) {
      throw new Error('Service not found');
    }
    
    return mapProcessToStatus(processes[0]);
  } finally {
    pm2.disconnect();
  }
}

export async function startService(serviceName: string): Promise<void> {
  await connectPM2();
  
  try {
    await startProcess(serviceName);
  } finally {
    pm2.disconnect();
  }
}

export async function stopService(serviceName: string): Promise<void> {
  await connectPM2();
  
  try {
    await stopProcess(serviceName);
  } finally {
    pm2.disconnect();
  }
}
