export function createLogger(name: string) {
  return {
    info: (message: string, ...args: any[]) => {
      console.log(`[${name}] INFO:`, message, ...args);
    },
    error: (message: string, ...args: any[]) => {
      console.error(`[${name}] ERROR:`, message, ...args);
    },
    warn: (message: string, ...args: any[]) => {
      console.warn(`[${name}] WARN:`, message, ...args);
    },
    debug: (message: string, ...args: any[]) => {
      console.log(`[${name}] DEBUG:`, message, ...args);
    }
  };
}