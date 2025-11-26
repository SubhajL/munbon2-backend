import * as fs from "fs";
import * as path from "path";
import * as os from "os";

export type TempWorkspace = {
  dir: string;
  screenshotDir: string;
  cleanup: () => void;
};

export function createTempWorkspace(
  prefix: string = "munbon-report",
): TempWorkspace {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), `${prefix}-`));
  const screenshotDir = path.join(dir, "screenshots");
  fs.mkdirSync(screenshotDir, { recursive: true });

  return {
    dir,
    screenshotDir,
    cleanup: () => {
      try {
        fs.rmSync(dir, { recursive: true, force: true });
      } catch {
        // Ignore cleanup errors
      }
    },
  };
}

export function ensureDir(dirPath: string): void {
  if (!fs.existsSync(dirPath)) {
    fs.mkdirSync(dirPath, { recursive: true });
  }
}
