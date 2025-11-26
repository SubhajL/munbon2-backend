import { Client } from "ssh2";
import * as fs from "fs";
import type { Config } from "./types";
import { logger } from "./utils/logger";

const DEFAULT_LOG_LINES = 2000;
const SSH_TIMEOUT_MS = 30000;

export function buildLogCommand(
  logPath: string,
  lines: number = DEFAULT_LOG_LINES,
): string {
  return `tail -n ${lines} ${logPath}`;
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

          if (code !== 0 && errorOutput) {
            logger.warn(
              { code, errorOutput },
              "Command exited with non-zero code",
            );
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
