const {
  RealtimeControlService,
} = require("../../src/services/realtimeControlService");
const { describe, test, expect, beforeEach } = require("@jest/globals");

describe("RealtimeControlService", () => {
  let service;
  let mockRepository;
  let mockValveService;
  let mockLogger;

  beforeEach(() => {
    mockRepository = {
      getSensorPlotMapping: jest.fn(),
      getControlThresholds: jest.fn(),
      getValveState: jest.fn(),
      updateValveState: jest.fn(),
      logControlDecision: jest.fn().mockResolvedValue(1),
      updateDecisionLogResult: jest.fn(),
      getPlotConfiguration: jest.fn(),
    };

    mockValveService = {
      sendValveCommandWithRetry: jest.fn().mockResolvedValue({
        success: true,
        valveName: "SV_SF01",
        level: 1,
      }),
    };

    mockLogger = {
      info: jest.fn(),
      warn: jest.fn(),
      error: jest.fn(),
    };

    service = new RealtimeControlService(
      mockRepository,
      mockValveService,
      mockLogger,
      { moistureFreshnessWindowMs: 300000 }, // 5 minutes default
    );
  });

  describe("constructor", () => {
    test("uses default 300000ms when moistureFreshnessWindowMs is NaN", () => {
      const serviceWithNaN = new RealtimeControlService(
        mockRepository,
        mockValveService,
        mockLogger,
        { moistureFreshnessWindowMs: NaN },
      );

      expect(serviceWithNaN.moistureFreshnessWindowMs).toBe(300000);
      expect(mockLogger.warn).toHaveBeenCalledWith(
        { configuredWindow: NaN },
        expect.stringContaining("Invalid moistureFreshnessWindowMs"),
      );
    });

    test("uses default 300000ms when moistureFreshnessWindowMs is negative", () => {
      const serviceWithNegative = new RealtimeControlService(
        mockRepository,
        mockValveService,
        mockLogger,
        { moistureFreshnessWindowMs: -1000 },
      );

      expect(serviceWithNegative.moistureFreshnessWindowMs).toBe(300000);
      expect(mockLogger.warn).toHaveBeenCalledWith(
        { configuredWindow: -1000 },
        expect.stringContaining("Invalid moistureFreshnessWindowMs"),
      );
    });

    test("accepts zero as valid freshness window", () => {
      const serviceWithZero = new RealtimeControlService(
        mockRepository,
        mockValveService,
        mockLogger,
        { moistureFreshnessWindowMs: 0 },
      );

      expect(serviceWithZero.moistureFreshnessWindowMs).toBe(0);
      expect(mockLogger.warn).not.toHaveBeenCalled();
    });

    test("accepts positive numbers as valid freshness window", () => {
      const serviceWithCustom = new RealtimeControlService(
        mockRepository,
        mockValveService,
        mockLogger,
        { moistureFreshnessWindowMs: 60000 },
      );

      expect(serviceWithCustom.moistureFreshnessWindowMs).toBe(60000);
      expect(mockLogger.warn).not.toHaveBeenCalled();
    });
  });

  describe("getReadingAge", () => {
    let dateNowSpy;

    beforeEach(() => {
      dateNowSpy = jest.spyOn(Date, "now").mockReturnValue(1000000000);
    });

    afterEach(() => {
      dateNowSpy.mockRestore();
    });

    test("returns age in milliseconds for Date timestamp", () => {
      const timestamp = new Date(1000000000 - 5000);

      const ageMs = service.getReadingAge(timestamp);

      expect(ageMs).toBe(5000);
    });

    test("returns age in milliseconds for ISO string timestamp", () => {
      const timestamp = new Date(1000000000 - 10000).toISOString();

      const ageMs = service.getReadingAge(timestamp);

      expect(ageMs).toBe(10000);
    });

    test("returns NaN for invalid timestamp string", () => {
      const ageMs = service.getReadingAge("invalid-date-string");

      expect(Number.isNaN(ageMs)).toBe(true);
    });

    test("returns NaN for undefined timestamp", () => {
      const ageMs = service.getReadingAge(undefined);

      expect(Number.isNaN(ageMs)).toBe(true);
    });

    test("returns age for null timestamp as Unix epoch", () => {
      const ageMs = service.getReadingAge(null);

      expect(ageMs).toBeGreaterThan(0);
      expect(Number.isNaN(ageMs)).toBe(false);
    });
  });

  describe("isReadingFresh", () => {
    let dateNowSpy;

    beforeEach(() => {
      dateNowSpy = jest.spyOn(Date, "now").mockReturnValue(1000000000);
    });

    afterEach(() => {
      dateNowSpy.mockRestore();
    });

    test("returns true when reading age is within freshness window", () => {
      const freshTimestamp = new Date(1000000000 - 100000);

      expect(service.isReadingFresh(freshTimestamp)).toBe(true);
    });

    test("returns true when reading age exactly equals freshness window", () => {
      const exactTimestamp = new Date(1000000000 - 300000);

      expect(service.isReadingFresh(exactTimestamp)).toBe(true);
    });

    test("returns false when reading age exceeds freshness window", () => {
      const staleTimestamp = new Date(1000000000 - 300001);

      expect(service.isReadingFresh(staleTimestamp)).toBe(false);
    });

    test("returns false for invalid timestamp", () => {
      expect(service.isReadingFresh("invalid-date")).toBe(false);
    });

    test("respects custom freshness window configuration", () => {
      const customService = new RealtimeControlService(
        mockRepository,
        mockValveService,
        mockLogger,
        { moistureFreshnessWindowMs: 60000 },
      );

      const timestamp50s = new Date(1000000000 - 50000);
      const timestamp70s = new Date(1000000000 - 70000);

      expect(customService.isReadingFresh(timestamp50s)).toBe(true);
      expect(customService.isReadingFresh(timestamp70s)).toBe(false);
    });

    test("allows zero freshness window to reject all readings", () => {
      const zeroWindowService = new RealtimeControlService(
        mockRepository,
        mockValveService,
        mockLogger,
        { moistureFreshnessWindowMs: 0 },
      );

      const veryRecentTimestamp = new Date(1000000000 - 1);

      expect(zeroWindowService.isReadingFresh(veryRecentTimestamp)).toBe(false);
    });
  });

  describe("evaluateControlDecision", () => {
    describe("Moisture sensor", () => {
      const thresholds = {
        moistureLowerThreshold: 10.0,
        moistureUpperThreshold: 15.0,
      };

      test("below lower threshold returns TURN_ON", () => {
        const decision = service.evaluateControlDecision({
          value: 9.5,
          sensorType: "moisture",
          thresholds,
          currentState: "OFF",
        });

        expect(decision).toEqual({
          action: "TURN_ON",
          newState: "ON",
          reason: expect.stringContaining("below"),
          value: 9.5,
          thresholds: {
            lower: 10.0,
            upper: 15.0,
          },
        });
      });

      test("exactly at lower threshold returns TURN_ON", () => {
        const decision = service.evaluateControlDecision({
          value: 10.0,
          sensorType: "moisture",
          thresholds,
          currentState: "OFF",
        });

        expect(decision.action).toBe("TURN_ON");
      });

      test("within hysteresis band returns MAINTAIN", () => {
        const decision = service.evaluateControlDecision({
          value: 12.5,
          sensorType: "moisture",
          thresholds,
          currentState: "ON",
        });

        expect(decision.action).toBe("MAINTAIN");
        expect(decision.newState).toBe("ON");
      });

      test("above upper threshold returns TURN_OFF", () => {
        const decision = service.evaluateControlDecision({
          value: 15.5,
          sensorType: "moisture",
          thresholds,
          currentState: "ON",
        });

        expect(decision).toEqual({
          action: "TURN_OFF",
          newState: "OFF",
          reason: expect.stringContaining("above"),
          value: 15.5,
          thresholds: {
            lower: 10.0,
            upper: 15.0,
          },
        });
      });

      test("exactly at upper threshold returns TURN_OFF", () => {
        const decision = service.evaluateControlDecision({
          value: 15.0,
          sensorType: "moisture",
          thresholds,
          currentState: "ON",
        });

        expect(decision.action).toBe("TURN_OFF");
      });

      test("negative value returns MAINTAIN with invalid reason", () => {
        const decision = service.evaluateControlDecision({
          value: -5.0,
          sensorType: "moisture",
          thresholds,
          currentState: "OFF",
        });

        expect(decision.action).toBe("MAINTAIN");
        expect(decision.reason).toContain("Invalid");
      });

      test("value over 100 percent returns MAINTAIN with invalid reason", () => {
        const decision = service.evaluateControlDecision({
          value: 105.0,
          sensorType: "moisture",
          thresholds,
          currentState: "ON",
        });

        expect(decision.action).toBe("MAINTAIN");
        expect(decision.reason).toContain("Invalid");
      });
    });

    describe("Water level sensor", () => {
      const thresholds = {
        waterLevelLowerThreshold: 5.0,
        waterLevelUpperThreshold: 15.0,
      };

      test("below lower threshold returns TURN_ON", () => {
        const decision = service.evaluateControlDecision({
          value: 4.0,
          sensorType: "water_level",
          thresholds,
          currentState: "OFF",
        });

        expect(decision.action).toBe("TURN_ON");
        expect(decision.reason).toContain("below");
      });

      test("above upper threshold returns TURN_OFF", () => {
        const decision = service.evaluateControlDecision({
          value: 16.0,
          sensorType: "water_level",
          thresholds,
          currentState: "ON",
        });

        expect(decision.action).toBe("TURN_OFF");
      });

      test("within hysteresis band returns MAINTAIN", () => {
        const decision = service.evaluateControlDecision({
          value: 10.0,
          sensorType: "water_level",
          thresholds,
          currentState: "ON",
        });

        expect(decision.action).toBe("MAINTAIN");
      });

      test("negative value returns MAINTAIN with invalid reason", () => {
        const decision = service.evaluateControlDecision({
          value: -2.0,
          sensorType: "water_level",
          thresholds,
          currentState: "ON",
        });

        expect(decision.action).toBe("MAINTAIN");
        expect(decision.reason).toContain("Invalid");
      });

      test("extremely large value returns TURN_OFF with overflow reason", () => {
        const decision = service.evaluateControlDecision({
          value: 1000.0,
          sensorType: "water_level",
          thresholds,
          currentState: "ON",
        });

        expect(decision.action).toBe("TURN_OFF");
        expect(decision.reason).toContain("overflow");
      });
    });

    describe("Validation", () => {
      test("missing currentState defaults to OFF safely", () => {
        const decision = service.evaluateControlDecision({
          value: 12.0,
          sensorType: "moisture",
          thresholds: {
            moistureLowerThreshold: 10.0,
            moistureUpperThreshold: 15.0,
          },
          currentState: null,
        });

        expect(decision.newState).toBe("OFF");
      });

      test("lower threshold equals upper throws validation error", () => {
        expect(() => {
          service.evaluateControlDecision({
            value: 12.0,
            sensorType: "moisture",
            thresholds: {
              moistureLowerThreshold: 10.0,
              moistureUpperThreshold: 10.0,
            },
            currentState: "OFF",
          });
        }).toThrow("Invalid thresholds");
      });

      test("lower threshold greater than upper throws validation error", () => {
        expect(() => {
          service.evaluateControlDecision({
            value: 12.0,
            sensorType: "moisture",
            thresholds: {
              moistureLowerThreshold: 15.0,
              moistureUpperThreshold: 10.0,
            },
            currentState: "OFF",
          });
        }).toThrow("Invalid thresholds");
      });

      test("null thresholds object throws validation error", () => {
        expect(() => {
          service.evaluateControlDecision({
            value: 12.0,
            sensorType: "moisture",
            thresholds: null,
            currentState: "OFF",
          });
        }).toThrow("Thresholds required");
      });

      test("unknown sensor type throws validation error", () => {
        expect(() => {
          service.evaluateControlDecision({
            value: 12.0,
            sensorType: "unknown",
            thresholds: {
              moistureLowerThreshold: 10.0,
              moistureUpperThreshold: 15.0,
            },
            currentState: "OFF",
          });
        }).toThrow("Invalid sensor type");
      });
    });
  });

  describe("handleSensorReading - Orchestration", () => {
    test("unmapped sensor skips processing without crash", async () => {
      mockRepository.getSensorPlotMapping.mockResolvedValue(null);

      await service.handleSensorReading({
        sensorId: "UNKNOWN",
        value: 10.0,
        timestamp: new Date(),
        sensorType: "moisture",
      });

      expect(mockLogger.warn).toHaveBeenCalled();
      expect(mockValveService.sendValveCommandWithRetry).not.toHaveBeenCalled();
    });

    test("unconfigured plot logs warning and skips", async () => {
      mockRepository.getSensorPlotMapping.mockResolvedValue({
        plotId: "TEST-PLOT",
        sensorType: "moisture",
      });
      mockRepository.getControlThresholds.mockResolvedValue(null);

      await service.handleSensorReading({
        sensorId: "SENSOR-01",
        value: 10.0,
        timestamp: new Date(),
        sensorType: "moisture",
      });

      expect(mockLogger.warn).toHaveBeenCalled();
      expect(mockValveService.sendValveCommandWithRetry).not.toHaveBeenCalled();
    });

    test("decision MAINTAIN does not send valve command", async () => {
      mockRepository.getSensorPlotMapping.mockResolvedValue({
        plotId: "TEST-PLOT",
        sensorType: "moisture",
      });
      mockRepository.getControlThresholds.mockResolvedValue({
        moistureLowerThreshold: 10.0,
        moistureUpperThreshold: 15.0,
      });
      mockRepository.getValveState.mockResolvedValue({
        currentState: "ON",
      });

      await service.handleSensorReading({
        sensorId: "SENSOR-01",
        value: 12.0,
        timestamp: new Date(),
        sensorType: "moisture",
      });

      expect(mockRepository.logControlDecision).toHaveBeenCalled();
      expect(mockValveService.sendValveCommandWithRetry).not.toHaveBeenCalled();
    });

    test("decision TURN_ON sends valve command and updates state", async () => {
      mockRepository.pool = {};
      mockRepository.getSensorPlotMapping.mockResolvedValue({
        plotId: "TEST-PLOT",
        sensorType: "moisture",
      });
      mockRepository.getControlThresholds.mockResolvedValue({
        moistureLowerThreshold: 10.0,
        moistureUpperThreshold: 15.0,
      });
      mockRepository.getValveState.mockResolvedValue({
        currentState: "OFF",
      });

      await service.handleSensorReading({
        sensorId: "SENSOR-01",
        value: 8.0,
        timestamp: new Date(),
        sensorType: "moisture",
      });

      expect(mockValveService.sendValveCommandWithRetry).toHaveBeenCalledWith(
        "TEST-PLOT",
        1,
        expect.any(Date),
        expect.stringContaining("below"),
      );
      expect(mockRepository.updateValveState).toHaveBeenCalledWith(
        mockRepository.pool,
        "TEST-PLOT",
        "ON",
        expect.any(String),
      );
      expect(mockRepository.updateDecisionLogResult).toHaveBeenCalledWith(
        mockRepository.pool,
        1,
        true,
      );
    });

    test("valve command failure recorded in decision log", async () => {
      mockRepository.pool = {};
      mockRepository.getSensorPlotMapping.mockResolvedValue({
        plotId: "TEST-PLOT",
        sensorType: "moisture",
      });
      mockRepository.getControlThresholds.mockResolvedValue({
        moistureLowerThreshold: 10.0,
        moistureUpperThreshold: 15.0,
      });
      mockRepository.getValveState.mockResolvedValue({
        currentState: "OFF",
      });
      mockValveService.sendValveCommandWithRetry.mockRejectedValue(
        new Error("Network timeout"),
      );

      await service.handleSensorReading({
        sensorId: "SENSOR-01",
        value: 8.0,
        timestamp: new Date(),
        sensorType: "moisture",
      });

      expect(mockRepository.updateDecisionLogResult).toHaveBeenCalledWith(
        mockRepository.pool,
        1,
        false,
        "Network timeout",
      );
    });

    test("stale moisture reading skips valve command and logs warning", async () => {
      const staleTimestamp = new Date(Date.now() - 400000); // 6 minutes 40 seconds old

      mockRepository.pool = {};
      mockRepository.getSensorPlotMapping.mockResolvedValue({
        plotId: "TEST-PLOT",
        sensorType: "moisture",
      });
      mockRepository.getControlThresholds.mockResolvedValue({
        moistureLowerThreshold: 10.0,
        moistureUpperThreshold: 15.0,
      });
      mockRepository.getValveState.mockResolvedValue({
        currentState: "OFF",
      });

      await service.handleSensorReading({
        sensorId: "SENSOR-01",
        value: 8.0,
        timestamp: staleTimestamp,
        sensorType: "moisture",
      });

      expect(mockLogger.warn).toHaveBeenCalledWith(
        expect.objectContaining({
          sensorId: "SENSOR-01",
          ageMs: expect.any(Number),
        }),
        expect.stringContaining("Stale moisture reading ignored"),
      );
      expect(mockValveService.sendValveCommandWithRetry).not.toHaveBeenCalled();
      expect(mockRepository.logControlDecision).not.toHaveBeenCalled();
    });

    test("fresh moisture reading triggers valve command normally", async () => {
      const freshTimestamp = new Date(Date.now() - 60000); // 1 minute old

      mockRepository.pool = {};
      mockRepository.getSensorPlotMapping.mockResolvedValue({
        plotId: "TEST-PLOT",
        sensorType: "moisture",
      });
      mockRepository.getControlThresholds.mockResolvedValue({
        moistureLowerThreshold: 10.0,
        moistureUpperThreshold: 15.0,
      });
      mockRepository.getValveState.mockResolvedValue({
        currentState: "OFF",
      });

      await service.handleSensorReading({
        sensorId: "SENSOR-01",
        value: 8.0,
        timestamp: freshTimestamp,
        sensorType: "moisture",
      });

      expect(mockLogger.warn).not.toHaveBeenCalledWith(
        expect.anything(),
        expect.stringContaining("Stale"),
      );
      expect(mockValveService.sendValveCommandWithRetry).toHaveBeenCalled();
      expect(mockRepository.logControlDecision).toHaveBeenCalled();
    });

    test("water level readings always process regardless of timestamp", async () => {
      const staleTimestamp = new Date(Date.now() - 400000); // 6 minutes 40 seconds old

      mockRepository.pool = {};
      mockRepository.getSensorPlotMapping.mockResolvedValue({
        plotId: "TEST-PLOT",
        sensorType: "water_level",
      });
      mockRepository.getControlThresholds.mockResolvedValue({
        waterLevelLowerThreshold: 5.0,
        waterLevelUpperThreshold: 15.0,
      });
      mockRepository.getValveState.mockResolvedValue({
        currentState: "OFF",
      });

      await service.handleSensorReading({
        sensorId: "SENSOR-01",
        value: 4.0,
        timestamp: staleTimestamp,
        sensorType: "water_level",
      });

      expect(mockLogger.warn).not.toHaveBeenCalledWith(
        expect.anything(),
        expect.stringContaining("Stale"),
      );
      expect(mockValveService.sendValveCommandWithRetry).toHaveBeenCalled();
      expect(mockRepository.logControlDecision).toHaveBeenCalled();
    });

    test("invalid moisture timestamp skips valve command and logs warning", async () => {
      mockRepository.pool = {};
      mockRepository.getSensorPlotMapping.mockResolvedValue({
        plotId: "TEST-PLOT",
        sensorType: "moisture",
      });

      await service.handleSensorReading({
        sensorId: "SENSOR-01",
        value: 8.0,
        timestamp: "invalid-timestamp",
        sensorType: "moisture",
      });

      expect(mockLogger.warn).toHaveBeenCalledWith(
        expect.objectContaining({
          sensorId: "SENSOR-01",
          timestamp: "invalid-timestamp",
        }),
        expect.stringContaining("Invalid moisture timestamp"),
      );
      expect(mockValveService.sendValveCommandWithRetry).not.toHaveBeenCalled();
      expect(mockRepository.logControlDecision).not.toHaveBeenCalled();
    });
  });

  describe("Audit logging integration", () => {
    let mockValveAuditService;

    beforeEach(() => {
      mockValveAuditService = {
        logValveChange: jest.fn().mockResolvedValue(42),
        updateCommandResult: jest.fn().mockResolvedValue(undefined),
      };
    });

    test("logs audit with fallback mode when plot config missing", async () => {
      mockRepository.getSensorPlotMapping.mockResolvedValue({
        plotId: "plot-no-config",
        sensorType: "moisture",
      });

      mockRepository.getControlThresholds.mockResolvedValue({
        moistureLowerThreshold: 40,
        moistureUpperThreshold: 60,
        waterLevelLowerThreshold: 5,
        waterLevelUpperThreshold: 15,
      });

      mockRepository.getValveState.mockResolvedValue({
        currentState: "OFF",
        lastChangedAt: null,
        lastChangeReason: null,
      });

      mockRepository.getPlotConfiguration.mockResolvedValue(null);

      mockValveService.valveMapping = new Map([["plot-no-config", "SV_TEST"]]);
      mockValveService.tableName = "tb_valve_command_v2_test";

      const serviceWithAudit = new RealtimeControlService(
        mockRepository,
        mockValveService,
        mockLogger,
        {},
        mockValveAuditService,
      );

      await serviceWithAudit.handleSensorReading({
        sensorId: "MOIST-01",
        value: 35,
        timestamp: new Date(),
        sensorType: "moisture",
      });

      expect(mockValveAuditService.logValveChange).toHaveBeenCalledWith(
        expect.objectContaining({
          plotId: "plot-no-config",
          controlMode: "MOISTURE",
          action: "TURN_ON",
        }),
      );

      expect(mockValveAuditService.updateCommandResult).toHaveBeenCalledWith(
        42,
        true,
      );
    });

    test("updates audit on command success", async () => {
      mockRepository.getSensorPlotMapping.mockResolvedValue({
        plotId: "plot-success",
        sensorType: "moisture",
      });

      mockRepository.getControlThresholds.mockResolvedValue({
        moistureLowerThreshold: 40,
        moistureUpperThreshold: 60,
        waterLevelLowerThreshold: 5,
        waterLevelUpperThreshold: 15,
      });

      mockRepository.getValveState.mockResolvedValue({
        currentState: "OFF",
      });

      mockRepository.getPlotConfiguration.mockResolvedValue({
        plotId: "plot-success",
        controlMode: "MOISTURE",
        cropType: "rice",
      });

      mockValveService.valveMapping = new Map([["plot-success", "SV_SUCCESS"]]);
      mockValveService.tableName = "tb_valve_command_v2_test";
      mockValveService.sendValveCommandWithRetry.mockResolvedValue({
        success: true,
      });

      const serviceWithAudit = new RealtimeControlService(
        mockRepository,
        mockValveService,
        mockLogger,
        {},
        mockValveAuditService,
      );

      await serviceWithAudit.handleSensorReading({
        sensorId: "MOIST-01",
        value: 35,
        timestamp: new Date(),
        sensorType: "moisture",
      });

      expect(mockValveAuditService.logValveChange).toHaveBeenCalled();
      expect(mockValveAuditService.updateCommandResult).toHaveBeenCalledWith(
        42,
        true,
      );
    });

    test("updates audit on command failure", async () => {
      mockRepository.getSensorPlotMapping.mockResolvedValue({
        plotId: "plot-fail",
        sensorType: "moisture",
      });

      mockRepository.getControlThresholds.mockResolvedValue({
        moistureLowerThreshold: 40,
        moistureUpperThreshold: 60,
        waterLevelLowerThreshold: 5,
        waterLevelUpperThreshold: 15,
      });

      mockRepository.getValveState.mockResolvedValue({
        currentState: "OFF",
      });

      mockRepository.getPlotConfiguration.mockResolvedValue({
        plotId: "plot-fail",
        controlMode: "MOISTURE",
        cropType: "rice",
      });

      mockValveService.valveMapping = new Map([["plot-fail", "SV_FAIL"]]);
      mockValveService.tableName = "tb_valve_command_v2_test";
      mockValveService.sendValveCommandWithRetry.mockRejectedValue(
        new Error("MSSQL connection timeout"),
      );

      const serviceWithAudit = new RealtimeControlService(
        mockRepository,
        mockValveService,
        mockLogger,
        {},
        mockValveAuditService,
      );

      await serviceWithAudit.handleSensorReading({
        sensorId: "MOIST-01",
        value: 35,
        timestamp: new Date(),
        sensorType: "moisture",
      });

      expect(mockValveAuditService.logValveChange).toHaveBeenCalled();
      expect(mockValveAuditService.updateCommandResult).toHaveBeenCalledWith(
        42,
        false,
        "MSSQL connection timeout",
      );
    });
  });
});
