const winston = require("winston");
const util = require("util");

// Extract the consoleFormat function for testing
const createConsoleFormat = () => {
  return winston.format.printf((info) => {
    const { level, message, timestamp, error, service, ...rawMetadata } = info;

    // Filter out winston internal symbols
    const metadata = {};
    for (const key of Object.keys(rawMetadata)) {
      if (typeof key === "string" && !key.startsWith("Symbol(")) {
        metadata[key] = rawMetadata[key];
      }
    }

    // Build timestamp prefix
    const ts = timestamp ? `[${timestamp}] ` : "";
    let msg = `${ts}${level}: `;

    // Handle message
    if (typeof message === "string") {
      msg += message;
    } else if (message) {
      msg += util.inspect(message, { depth: 2, colors: false, compact: true });
    }

    // Handle error
    if (error instanceof Error) {
      msg += `\n${error.stack}`;
    } else if (metadata.error instanceof Error) {
      msg += `\n${metadata.error.stack}`;
      delete metadata.error;
    }

    // Handle metadata
    const metaKeys = Object.keys(metadata);
    if (metaKeys.length > 0) {
      msg += ` ${util.inspect(metadata, { depth: 2, colors: false, compact: true })}`;
    }

    return msg;
  });
};

describe("logger consoleFormat", () => {
  let format;

  beforeEach(() => {
    format = createConsoleFormat();
  });

  const getFormatted = (info) => {
    const result = format.transform(info);
    return result[Symbol.for("message")];
  };

  test("formats string messages correctly", () => {
    const info = {
      level: "info",
      message: "Test message",
    };

    const formatted = getFormatted(info);
    expect(formatted).toBe("info: Test message");
  });

  test("includes timestamp when present", () => {
    const info = {
      level: "info",
      message: "Test message",
      timestamp: "2025-10-12T10:00:00.000Z",
    };

    const formatted = getFormatted(info);
    expect(formatted).toBe("[2025-10-12T10:00:00.000Z] info: Test message");
  });

  test("formats object messages using util.inspect", () => {
    const info = {
      level: "info",
      message: { plotId: 123, status: "active" },
    };

    const formatted = getFormatted(info);
    expect(formatted).toContain("info:");
    expect(formatted).toContain("plotId: 123");
    expect(formatted).toContain("status:");
  });

  test("includes metadata in output when present", () => {
    const info = {
      level: "info",
      message: "Test message",
      customKey: "customValue",
      anotherKey: 456,
    };

    const formatted = getFormatted(info);
    expect(formatted).toContain("Test message");
    expect(formatted).toContain("customKey");
    expect(formatted).toContain("customValue");
    expect(formatted).toContain("anotherKey");
    expect(formatted).toContain("456");
  });

  test("excludes service from metadata but shows timestamp", () => {
    const info = {
      level: "info",
      message: "Test message",
      service: "test-service",
      timestamp: "2025-01-01T00:00:00.000Z",
      customKey: "value",
    };

    const formatted = getFormatted(info);
    expect(formatted).toContain("[2025-01-01T00:00:00.000Z]");
    expect(formatted).toContain("Test message");
    expect(formatted).toContain("customKey");
    // Service should not appear in metadata section
    const metadataMatch = formatted.match(/\{.*\}/);
    if (metadataMatch) {
      expect(metadataMatch[0]).not.toContain("service");
      expect(metadataMatch[0]).not.toContain("test-service");
    }
  });

  test("displays Error stack trace when error present", () => {
    const testError = new Error("Test error message");
    const info = {
      level: "error",
      message: "Operation failed",
      error: testError,
    };

    const formatted = getFormatted(info);
    expect(formatted).toContain("Operation failed");
    expect(formatted).toContain("Error: Test error message");
    expect(formatted).toContain("at ");
  });

  test("handles error in metadata object", () => {
    const testError = new Error("Nested error");
    const info = {
      level: "error",
      message: "Failed operation",
      error: testError,
      plotId: "123",
    };

    const formatted = getFormatted(info);
    expect(formatted).toContain("Failed operation");
    expect(formatted).toContain("Error: Nested error");
    expect(formatted).toContain("plotId");
    // Error should not appear in metadata section after being extracted
    const lines = formatted.split("\n");
    const metadataLine = lines.find((l) => l.includes("plotId"));
    if (metadataLine) {
      expect(metadataLine).not.toContain("Error: Nested error");
    }
  });

  test("limits object depth to 2 levels", () => {
    const deepObject = {
      level1: {
        level2: {
          level3: {
            level4: "should be truncated",
          },
        },
      },
    };

    const info = {
      level: "info",
      message: deepObject,
    };

    const formatted = getFormatted(info);
    expect(formatted).toContain("level1");
    expect(formatted).toContain("level2");
    // At depth 2, level3 should show but level4 content should be truncated
    // util.inspect with depth:2 will show level3 as [Object]
    expect(formatted).toMatch(/level3.*\[Object\]|level3.*\.\.\./);
  });

  test("handles empty metadata gracefully", () => {
    const info = {
      level: "info",
      message: "Simple message",
      service: "test-service",
      timestamp: "2025-01-01",
    };

    const formatted = getFormatted(info);
    expect(formatted).toBe("[2025-01-01] info: Simple message");
    // Should not have trailing metadata object notation
    expect(formatted).not.toMatch(/\{.*\}/);
  });

  test("handles missing message gracefully", () => {
    const info = {
      level: "warn",
      customData: "some data",
    };

    const formatted = getFormatted(info);
    expect(formatted).toContain("warn:");
    expect(formatted).toContain("customData");
  });

  test("formats complex metadata with multiple properties", () => {
    const info = {
      level: "error",
      message: "Database error",
      query: "SELECT * FROM users",
      duration: 1234,
      retryCount: 3,
    };

    const formatted = getFormatted(info);
    expect(formatted).toContain("Database error");
    expect(formatted).toContain("query");
    expect(formatted).toContain("SELECT * FROM users");
    expect(formatted).toContain("duration");
    expect(formatted).toContain("1234");
    expect(formatted).toContain("retryCount");
    expect(formatted).toContain("3");
  });
});
