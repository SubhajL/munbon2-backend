import { describe, expect, test, afterEach } from "vitest";
import * as fs from "fs";
import * as path from "path";
import { createTempWorkspace, ensureDir } from "./temp";

describe("createTempWorkspace", () => {
  let workspace: ReturnType<typeof createTempWorkspace> | null = null;

  afterEach(() => {
    workspace?.cleanup();
    workspace = null;
  });

  test("creates temp directory with prefix", () => {
    workspace = createTempWorkspace("test-prefix");

    expect(fs.existsSync(workspace.dir)).toBe(true);
    expect(workspace.dir).toContain("test-prefix");
  });

  test("creates screenshots subdirectory", () => {
    workspace = createTempWorkspace();

    expect(fs.existsSync(workspace.screenshotDir)).toBe(true);
    expect(workspace.screenshotDir).toBe(
      path.join(workspace.dir, "screenshots"),
    );
  });

  test("cleanup removes entire directory tree", () => {
    workspace = createTempWorkspace();
    const dir = workspace.dir;

    const testFile = path.join(workspace.screenshotDir, "test.txt");
    fs.writeFileSync(testFile, "test");

    workspace.cleanup();
    workspace = null;

    expect(fs.existsSync(dir)).toBe(false);
  });
});

describe("ensureDir", () => {
  test("creates directory if it does not exist", () => {
    const tempDir = path.join(
      require("os").tmpdir(),
      `ensure-test-${Date.now()}`,
    );

    try {
      expect(fs.existsSync(tempDir)).toBe(false);
      ensureDir(tempDir);
      expect(fs.existsSync(tempDir)).toBe(true);
    } finally {
      fs.rmSync(tempDir, { recursive: true, force: true });
    }
  });

  test("does not throw if directory already exists", () => {
    const tempDir = path.join(
      require("os").tmpdir(),
      `ensure-existing-${Date.now()}`,
    );

    try {
      fs.mkdirSync(tempDir);
      expect(() => ensureDir(tempDir)).not.toThrow();
    } finally {
      fs.rmSync(tempDir, { recursive: true, force: true });
    }
  });
});
