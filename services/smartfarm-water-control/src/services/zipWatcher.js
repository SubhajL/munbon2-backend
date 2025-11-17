const fs = require('fs');
const path = require('path');
const { unzipAndParse } = require('./unzipAndParse');

class ZipWatcher {
  constructor({ dir, logger }) {
    this.dir = dir || '/datauploads';
    this.logger = logger || console;
    if (!fs.existsSync(this.dir)) fs.mkdirSync(this.dir, { recursive: true });
    this.processedDir = path.join(this.dir, 'processed');
    this.failedDir = path.join(this.dir, 'failed');
    for (const d of [this.processedDir, this.failedDir]) if (!fs.existsSync(d)) fs.mkdirSync(d, { recursive: true });
  }

  start() {
    fs.watch(this.dir, { persistent: true }, (event, filename) => {
      if (!filename) return;
      const match = filename.match(/^\d{8}-moisturesensors\.zip$/i);
      if (match) {
        const filePath = path.join(this.dir, filename);
        setTimeout(() => this.onFile(filePath).catch(e=>this.logger.error(e)), 500);
      }
    });
    this.logger.info(`Watching ${this.dir} for moisture sensor ZIPs`);
  }

  async onFile(filePath) {
    try {
      const { count } = await unzipAndParse(filePath, this.logger);
      const dest = path.join(this.processedDir, path.basename(filePath));
      fs.renameSync(filePath, dest);
      this.logger.info(`Imported ${count} moisture sensors from ${path.basename(filePath)}`);
    } catch (e) {
      const dest = path.join(this.failedDir, path.basename(filePath));
      try { fs.renameSync(filePath, dest); } catch {}
      throw e;
    }
  }
}

module.exports = { ZipWatcher };