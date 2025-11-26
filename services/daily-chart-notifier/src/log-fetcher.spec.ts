import { describe, expect, test, vi, beforeEach } from "vitest";
import { fetchPm2Logs, buildLogCommand } from "./log-fetcher";
import type { Config } from "./types";

vi.mock("ssh2", () => {
  const mockStream = {
    on: vi.fn((event: string, callback: Function) => {
      if (event === "data") {
        callback(
          Buffer.from(
            "2024-01-15 13:00:00 Log line 1\n2024-01-15 14:00:00 Log line 2\n",
          ),
        );
      }
      if (event === "close") {
        setTimeout(() => callback(0), 10);
      }
      return mockStream;
    }),
    stderr: {
      on: vi.fn().mockReturnThis(),
    },
  };

  const mockConn = {
    on: vi.fn((event: string, callback: Function) => {
      if (event === "ready") {
        setTimeout(() => callback(), 10);
      }
      return mockConn;
    }),
    exec: vi.fn(
      (
        cmd: string,
        callback: (err: Error | null, stream: typeof mockStream) => void,
      ) => {
        callback(null, mockStream);
      },
    ),
    connect: vi.fn(),
    end: vi.fn(),
  };

  return {
    Client: vi.fn(() => mockConn),
  };
});

vi.mock("fs", async () => {
  const actual = await vi.importActual("fs");
  return {
    ...actual,
    readFileSync: vi.fn().mockReturnValue("fake-private-key"),
  };
});

const mockConfig: Config = {
  smtp: {
    host: "smtp.gmail.com",
    port: 587,
    user: "test@example.com",
    pass: "password",
    from: "Test <test@example.com>",
  },
  email: { to: "recipient@example.com" },
  ssh: {
    host: "192.168.1.1",
    port: 22,
    user: "ubuntu",
    keyPath: "/path/to/key.pem",
  },
  dashboards: {
    moistureUrl: "http://localhost:8080/moisture.html",
    waterLevelUrl: "http://localhost:8080/water.html",
  },
  pm2LogPath: "~/.pm2/logs/app-out.log",
  timezone: "Asia/Bangkok",
};

describe("buildLogCommand", () => {
  test("builds tail command for log file", () => {
    const logPath = "~/.pm2/logs/app-out.log";
    const lines = 1000;

    const command = buildLogCommand(logPath, lines);

    expect(command).toBe("tail -n 1000 ~/.pm2/logs/app-out.log");
  });

  test("uses default 2000 lines when not specified", () => {
    const logPath = "/var/log/app.log";

    const command = buildLogCommand(logPath);

    expect(command).toBe("tail -n 2000 /var/log/app.log");
  });
});

describe("fetchPm2Logs", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("connects to SSH with config settings", async () => {
    const { Client } = await import("ssh2");
    const mockClient = new Client();

    await fetchPm2Logs(mockConfig);

    expect(mockClient.connect).toHaveBeenCalledWith(
      expect.objectContaining({
        host: mockConfig.ssh.host,
        port: mockConfig.ssh.port,
        username: mockConfig.ssh.user,
      }),
    );
  });

  test("returns log content as string", async () => {
    const result = await fetchPm2Logs(mockConfig);

    expect(result).toContain("Log line 1");
    expect(result).toContain("Log line 2");
  });

  test("closes SSH connection after fetching", async () => {
    const { Client } = await import("ssh2");
    const mockClient = new Client();

    await fetchPm2Logs(mockConfig);

    expect(mockClient.end).toHaveBeenCalled();
  });

  test("returns empty string when no logs found", async () => {
    const { Client } = await import("ssh2");
    const mockClient = new Client();

    const mockStream = {
      on: vi.fn((event: string, callback: Function) => {
        if (event === "data") {
          // No data
        }
        if (event === "close") {
          setTimeout(() => callback(0), 10);
        }
        return mockStream;
      }),
      stderr: { on: vi.fn().mockReturnThis() },
    };

    mockClient.exec.mockImplementationOnce((cmd: string, cb: Function) => {
      cb(null, mockStream);
    });

    const result = await fetchPm2Logs(mockConfig);

    expect(result).toBe("");
  });
});
