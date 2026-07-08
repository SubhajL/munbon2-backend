export type Config = {
  smtp: {
    host: string;
    port: number;
    user: string;
    pass: string;
    from: string;
  };
  email: {
    to: string;
  };
  ssh: {
    host: string;
    port: number;
    user: string;
    keyPath: string;
  };
  dashboards: {
    moistureUrl: string;
    waterLevelUrl: string;
  };
  pm2LogPath: string;
  timezone: string;
};

export type Attachment = {
  filename: string;
  path?: string;
  content?: string | Buffer;
};

export type JobResult = {
  success: boolean;
  error?: string;
  screenshotPaths?: string[];
  logContent?: string;
};
