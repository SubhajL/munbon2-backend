import { Client } from "ssh2";
import * as fs from "fs";
import type { Config } from "./types";
import { logger } from "./utils/logger";

const DEFAULT_LOG_LINES = 2000;
const SSH_TIMEOUT_MS = 30000;
const SAFE_PATH_PATTERN = /^[a-zA-Z0-9_.~/-]+$/;

export class LogFetchError extends Error {
  constructor(
    message: string,
    public readonly exitCode?: number,
  ) {
    super(message);
    this.name = "LogFetchError";
  }
}

export function sanitizeLogPath(logPath: string): string {
  if (!logPath || logPath.length === 0) {
    throw new LogFetchError("Log path cannot be empty");
  }
  if (!SAFE_PATH_PATTERN.test(logPath)) {
    throw new LogFetchError("Invalid log path: contains unsafe characters");
  }
  if (logPath.includes("..")) {
    throw new LogFetchError("Invalid log path: path traversal not allowed");
  }
  return logPath;
}

export function buildLogCommand(
  logPath: string,
  lines: number = DEFAULT_LOG_LINES,
): string {
  const safePath = sanitizeLogPath(logPath);
  return `tail -n ${lines} ${safePath}`;
}

export async function fetchPm2Logs(
  config: Config,
  lines: number = DEFAULT_LOG_LINES,
): Promise<string> {
  return new Promise((resolve, reject) => {
    const conn = new Client();
    let output = "";
    let errorOutput = "";

    const timeout = setTimeout(() => {
      conn.end();
      reject(new Error("SSH connection timeout"));
    }, SSH_TIMEOUT_MS);

    conn.on("ready", () => {
      logger.info({ host: config.ssh.host }, "SSH connection established");

      const command = buildLogCommand(config.pm2LogPath, lines);
      logger.info({ command }, "Executing log fetch command");

      conn.exec(command, (err, stream) => {
        if (err) {
          clearTimeout(timeout);
          conn.end();
          reject(err);
          return;
        }

        stream.on("data", (data: Buffer) => {
          output += data.toString();
        });

        stream.stderr.on("data", (data: Buffer) => {
          errorOutput += data.toString();
        });

        stream.on("close", (code: number) => {
          clearTimeout(timeout);
          conn.end();

          if (code !== 0) {
            const errorMsg = errorOutput || "Unknown error";
            reject(
              new LogFetchError(
                `Log fetch failed with exit code ${code}: ${errorMsg}`,
                code,
              ),
            );
            return;
          }

          logger.info({ bytesReceived: output.length }, "Log fetch complete");
          resolve(output);
        });
      });
    });

    conn.on("error", (err) => {
      clearTimeout(timeout);
      logger.error({ err }, "SSH connection error");
      reject(err);
    });

    const privateKey = fs.readFileSync(config.ssh.keyPath);

    conn.connect({
      host: config.ssh.host,
      port: config.ssh.port,
      username: config.ssh.user,
      privateKey,
    });
  });
}
