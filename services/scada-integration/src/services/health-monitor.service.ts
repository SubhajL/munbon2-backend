import { scadaPool } from '../config/database';
import { 
  SiteInfo, 
  SiteHealthStatus, 
  ScadaHealthReport, 
  HealthStatus 
} from '../types/scada.types';

export class HealthMonitorService {
  private healthCheckInterval: number = 30000; // 30 seconds
  private cacheValidityMs: number = 30000; // 30 seconds
  private lastHealthReport: ScadaHealthReport | null = null;
  private lastCheckTime: Date | null = null;
  private monitoringTimer: NodeJS.Timer | null = null;

  // Thresholds for health evaluation
  private readonly STALE_THRESHOLD_MINUTES = {
    healthy: 5,
    degraded: 15,
    critical: 30
  };

  /**
   * Get current SCADA health status
   */
  async getHealthStatus(useCache: boolean = true): Promise<ScadaHealthReport> {
    // Return cached result if valid
    if (useCache && this.isCacheValid()) {
      return this.lastHealthReport!;
    }

    try {
      const sites = await this.getSiteStatuses();
      const report = this.evaluateOverallHealth(sites);
      
      // Cache the result
      this.lastHealthReport = report;
      this.lastCheckTime = new Date();
      
      return report;
    } catch (error) {
      console.error('Failed to get health status:', error);
      return this.createFailedReport('Database connection failed');
    }
  }

  /**
   * Get detailed site statuses
   */
  async getDetailedHealthStatus(): Promise<ScadaHealthReport> {
    const report = await this.getHealthStatus(false); // Don't use cache
    // Include detailed site information
    const sites = await this.getSiteStatuses();
    report.details = sites;
    return report;
  }

  /**
   * Query site statuses from database
   */
  private async getSiteStatuses(): Promise<SiteHealthStatus[]> {
    const query = `
      SELECT 
        stationcode,
        site_name,
        laststatus,
        dt_laststatus,
        EXTRACT(EPOCH FROM (NOW() - dt_laststatus)) / 60 as minutes_since_update
      FROM tb_site
      WHERE stationcode IS NOT NULL
      ORDER BY site_name
    `;

    const result = await scadaPool.query(query);
    
    return result.rows.map(row => ({
      stationcode: row.stationcode,
      site_name: row.site_name,
      status: row.laststatus,
      lastUpdateTime: row.dt_laststatus,
      minutesSinceUpdate: row.minutes_since_update ? Math.round(row.minutes_since_update) : null,
      health: this.evaluateSiteHealth(row.laststatus, row.minutes_since_update)
    }));
  }

  /**
   * Evaluate individual site health
   */
  private evaluateSiteHealth(status: string | null, minutesSinceUpdate: number | null): HealthStatus {
    // If no status data, consider it failed
    if (!status || !minutesSinceUpdate) {
      return HealthStatus.FAILED;
    }

    // If offline, it's at least critical
    if (status === 'OFFLINE') {
      return HealthStatus.CRITICAL;
    }

    // Evaluate based on data freshness
    if (minutesSinceUpdate <= this.STALE_THRESHOLD_MINUTES.healthy) {
      return HealthStatus.HEALTHY;
    } else if (minutesSinceUpdate <= this.STALE_THRESHOLD_MINUTES.degraded) {
      return HealthStatus.DEGRADED;
    } else if (minutesSinceUpdate <= this.STALE_THRESHOLD_MINUTES.critical) {
      return HealthStatus.CRITICAL;
    } else {
      return HealthStatus.FAILED;
    }
  }

  /**
   * Evaluate overall system health
   */
  private evaluateOverallHealth(sites: SiteHealthStatus[]): ScadaHealthReport {
    const totalSites = sites.length;
    const onlineSites = sites.filter(s => s.status === 'ONLINE').length;
    const offlineSites = sites.filter(s => s.status === 'OFFLINE').length;
    const staleDataSites = sites.filter(s => 
      s.minutesSinceUpdate && s.minutesSinceUpdate > this.STALE_THRESHOLD_MINUTES.healthy
    ).length;

    // Calculate percentages
    const onlinePercentage = totalSites > 0 ? (onlineSites / totalSites) * 100 : 0;
    const healthySites = sites.filter(s => s.health === HealthStatus.HEALTHY).length;
    const healthyPercentage = totalSites > 0 ? (healthySites / totalSites) * 100 : 0;

    // Determine overall status
    let overallStatus: HealthStatus;
    if (totalSites === 0) {
      overallStatus = HealthStatus.FAILED;
    } else if (healthyPercentage >= 90) {
      overallStatus = HealthStatus.HEALTHY;
    } else if (healthyPercentage >= 70 || onlinePercentage >= 80) {
      overallStatus = HealthStatus.DEGRADED;
    } else if (onlinePercentage >= 50) {
      overallStatus = HealthStatus.CRITICAL;
    } else {
      overallStatus = HealthStatus.FAILED;
    }

    return {
      status: overallStatus,
      totalSites,
      onlineSites,
      offlineSites,
      staleDataSites,
      lastCheck: new Date()
    };
  }

  /**
   * Create a failed health report
   */
  private createFailedReport(message: string): ScadaHealthReport {
    return {
      status: HealthStatus.FAILED,
      totalSites: 0,
      onlineSites: 0,
      offlineSites: 0,
      staleDataSites: 0,
      lastCheck: new Date()
    };
  }

  /**
   * Check if cached result is still valid
   */
  private isCacheValid(): boolean {
    if (!this.lastHealthReport || !this.lastCheckTime) {
      return false;
    }
    
    const ageMs = Date.now() - this.lastCheckTime.getTime();
    return ageMs < this.cacheValidityMs;
  }

  /**
   * Start periodic health monitoring
   */
  startMonitoring(): void {
    if (this.monitoringTimer) {
      console.log('Health monitoring already started');
      return;
    }

    console.log('Starting SCADA health monitoring...');
    
    // Initial check
    this.getHealthStatus(false).catch(console.error);
    
    // Periodic checks
    this.monitoringTimer = setInterval(() => {
      this.getHealthStatus(false).catch(console.error);
    }, this.healthCheckInterval);
  }

  /**
   * Stop health monitoring
   */
  stopMonitoring(): void {
    if (this.monitoringTimer) {
      clearInterval(this.monitoringTimer);
      this.monitoringTimer = null;
      console.log('SCADA health monitoring stopped');
    }
  }

  /**
   * Get specific site status
   */
  async getSiteStatus(stationCode: string): Promise<SiteHealthStatus | null> {
    const query = `
      SELECT 
        stationcode,
        site_name,
        laststatus,
        dt_laststatus,
        EXTRACT(EPOCH FROM (NOW() - dt_laststatus)) / 60 as minutes_since_update
      FROM tb_site
      WHERE stationcode = $1
    `;

    const result = await scadaPool.query(query, [stationCode]);
    
    if (result.rows.length === 0) {
      return null;
    }

    const row = result.rows[0];
    return {
      stationcode: row.stationcode,
      site_name: row.site_name,
      status: row.laststatus,
      lastUpdateTime: row.dt_laststatus,
      minutesSinceUpdate: row.minutes_since_update ? Math.round(row.minutes_since_update) : null,
      health: this.evaluateSiteHealth(row.laststatus, row.minutes_since_update)
    };
  }
}

// Export singleton instance
export const healthMonitorService = new HealthMonitorService();