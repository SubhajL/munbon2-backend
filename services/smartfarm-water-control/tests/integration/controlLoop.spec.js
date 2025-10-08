const { WaterController } = require("../../src/controllers/waterController");
const {
  MoistureControlService,
} = require("../../src/services/moistureControlService");
const { AWDControlService } = require("../../src/services/awdControlService");
const {
  ValveCommandService,
} = require("../../src/services/valveCommandService");
const {
  WaterPlanningService,
} = require("../../src/services/waterPlanningService");
const {
  WaterBalanceService,
} = require("../../src/services/waterBalanceService");

describe("Control Loop Integration Tests", () => {
  let controller;
  let mockServices;
  let mockConfig;

  beforeEach(() => {
    // Mock TimescaleDB repository
    const mockRepository = {
      pool: {},
      getLatestSensorReading: jest.fn(),
      getSensorHistory: jest.fn(),
      checkSensorHealth: jest.fn(),
      saveWaterDemand: jest.fn().mockResolvedValue(undefined),
      getPlannedDemand: jest.fn().mockResolvedValue(0),
      saveDailyProgress: jest.fn().mockResolvedValue(undefined),
      recordIrrigationCycle: jest.fn().mockResolvedValue(undefined),
      updateValveStatus: jest.fn().mockResolvedValue(undefined),
      getDailyWaterBalance: jest.fn().mockResolvedValue({
        total_usage_liters: 0,
        number_of_cycles: 0,
        average_duration_minutes: 0,
      }),
      getAggregatedUsageMetrics: jest.fn().mockResolvedValue([]),
      getControlThresholds: jest.fn((db, plotId) => {
        if (plotId === "SF01") {
          return Promise.resolve({
            plotId: "SF01",
            moistureLowerThreshold: 10,
            moistureUpperThreshold: 15,
            waterLevelLowerThreshold: 5,
            waterLevelUpperThreshold: 15,
          });
        }
        if (plotId === "SF06") {
          return Promise.resolve({
            plotId: "SF06",
            moistureLowerThreshold: 10,
            moistureUpperThreshold: 15,
            waterLevelLowerThreshold: 5,
            waterLevelUpperThreshold: 15,
          });
        }
        return Promise.resolve(null);
      }),
    };

    const mockMssqlPool = {
      request: jest.fn().mockReturnThis(),
      input: jest.fn().mockReturnThis(),
      query: jest.fn().mockResolvedValue({ rowsAffected: [1] }),
    };

    // Mock configuration
    mockConfig = {
      plots: [
        {
          plotId: "SF01",
          areaRai: 2.5,
          sensorId: "AWD-SF01",
          valveName: "SV_SF01",
          cropType: "rice",
        },
        {
          plotId: "SF06",
          areaRai: 2.5,
          sensorId: "MOIST-SF06",
          valveName: "SV_SF06",
          cropType: "rice",
        },
      ],
      control: {
        moisture: {
          thresholdLowPercent: 10,
          thresholdHighPercent: 15,
        },
        awd: {
          minWaterLevelCm: 5,
          maxWaterLevelCm: 15,
          dryingPeriodDays: 7,
        },
        waterFlowRateLPM: 60,
      },
    };

    // Create mock sensor data service
    const mockSensorData = {
      getSensorReading: jest.fn(),
      getSensorHistory: jest.fn(),
      checkSensorHealth: jest.fn(),
      clearCache: jest.fn(),
    };

    // Create mock control mode service
    const mockControlMode = {
      getMode: jest.fn((plotId) => {
        if (plotId === "SF01") return "AWD";
        if (plotId === "SF06") return "MOISTURE";
        throw new Error(`No control mode configured for plot: ${plotId}`);
      }),
      loadModes: jest.fn(),
      refreshIfStale: jest.fn(),
      getAllModes: jest.fn(),
      isCacheStale: jest.fn(),
    };

    // Create services
    mockServices = {
      timescaleRepository: mockRepository,
      controlMode: mockControlMode,
      moistureControl: new MoistureControlService(mockConfig.control.moisture),
      awdControl: new AWDControlService(mockConfig.control.awd),
      valveCommand: new ValveCommandService({
        mssqlPool: mockMssqlPool,
        timescaleRepository: mockRepository,
        valveMapping: new Map([
          ["SF01", "SV_SF01"],
          ["SF06", "SV_SF06"],
        ]),
        tableName: "tb_valve_command_v2",
      }),
      waterPlanning: new WaterPlanningService({
        timescaleRepository: mockRepository,
        rosApiUrl: "http://localhost:3001/api",
        rosApiKey: "test-key",
        rosEndpoint: "/v1/ros/demand/calculate",
        plotConfigs: mockConfig.plots,
      }),
      waterBalance: new WaterBalanceService({
        timescaleRepository: mockRepository,
        flowRateLPM: mockConfig.control.waterFlowRateLPM,
      }),
      sensorData: mockSensorData,
      config: mockConfig,
    };

    // Create controller
    controller = new WaterController(mockServices);

    // Spy on service methods
    jest.spyOn(mockServices.valveCommand, "sendValveCommand");
    jest.spyOn(mockServices.waterBalance, "startIrrigation");
    jest.spyOn(mockServices.waterBalance, "stopIrrigation");
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe("AWD Control Integration", () => {
    it("should turn ON valve when water level is below minimum", async () => {
      // Mock sensor reading
      mockServices.sensorData.getSensorReading.mockResolvedValue({
        sensorId: "AWD-SF01",
        type: "water-level",
        value: 3, // Below minimum of 5cm
        timestamp: new Date(),
        unit: "cm",
      });

      // Process plot
      const decision = await controller.processPlot(mockConfig.plots[0]);

      expect(decision.action).toBe("ON");
      expect(mockServices.valveCommand.sendValveCommand).toHaveBeenCalledWith(
        "SF01",
        1, // ON
        expect.any(Date),
        expect.any(String),
      );
      expect(mockServices.waterBalance.startIrrigation).toHaveBeenCalledWith(
        "SF01",
        "SV_SF01",
        "AWD",
        3,
      );
    });

    it("should turn OFF valve when water level reaches maximum", async () => {
      // Mock sensor reading
      mockServices.sensorData.getSensorReading.mockResolvedValue({
        sensorId: "AWD-SF01",
        type: "water-level",
        value: 16, // Above maximum of 15cm
        timestamp: new Date(),
        unit: "cm",
      });

      // Mock current valve status as ON
      mockServices.valveCommand.getValveStatus = jest.fn().mockResolvedValue({
        status: "ON",
      });

      // Process plot
      const decision = await controller.processPlot(mockConfig.plots[0]);

      expect(decision.action).toBe("OFF");
      expect(mockServices.valveCommand.sendValveCommand).toHaveBeenCalledWith(
        "SF01",
        0, // OFF
        expect.any(Date),
        expect.any(String),
      );
      expect(mockServices.waterBalance.stopIrrigation).toHaveBeenCalledWith(
        "SF01",
      );
    });
  });

  describe("Moisture Control Integration", () => {
    it("should turn ON valve when moisture is below low threshold", async () => {
      // Mock sensor reading
      mockServices.sensorData.getSensorReading.mockResolvedValue({
        sensorId: "MOIST-SF06",
        type: "moisture",
        value: 8, // Below low threshold of 10%
        timestamp: new Date(),
        unit: "%",
      });

      // Process plot
      const decision = await controller.processPlot(mockConfig.plots[1]);

      expect(decision.action).toBe("ON");
      expect(mockServices.valveCommand.sendValveCommand).toHaveBeenCalledWith(
        "SF06",
        1, // ON
        expect.any(Date),
        expect.any(String),
      );
      expect(mockServices.waterBalance.startIrrigation).toHaveBeenCalledWith(
        "SF06",
        "SV_SF06",
        "MOISTURE",
        8,
      );
    });

    it("should turn OFF valve when moisture exceeds high threshold", async () => {
      // Mock sensor reading
      mockServices.sensorData.getSensorReading.mockResolvedValue({
        sensorId: "MOIST-SF06",
        type: "moisture",
        value: 18, // Above high threshold of 15%
        timestamp: new Date(),
        unit: "%",
      });

      // Mock current valve status as ON
      mockServices.valveCommand.getValveStatus = jest.fn().mockResolvedValue({
        status: "ON",
      });

      // Process plot
      const decision = await controller.processPlot(mockConfig.plots[1]);

      expect(decision.action).toBe("OFF");
      expect(mockServices.valveCommand.sendValveCommand).toHaveBeenCalledWith(
        "SF06",
        0, // OFF
        expect.any(Date),
        expect.any(String),
      );
      expect(mockServices.waterBalance.stopIrrigation).toHaveBeenCalledWith(
        "SF06",
      );
    });

    it("should maintain state when moisture is between thresholds", async () => {
      // Mock sensor reading
      mockServices.sensorData.getSensorReading.mockResolvedValue({
        sensorId: "MOIST-SF06",
        type: "moisture",
        value: 12, // Between thresholds
        timestamp: new Date(),
        unit: "%",
      });

      // Process plot
      const decision = await controller.processPlot(mockConfig.plots[1]);

      expect(decision.action).toBe("MAINTAIN");
      expect(mockServices.valveCommand.sendValveCommand).not.toHaveBeenCalled();
    });
  });

  describe("Full Control Loop", () => {
    it("should process all plots in control loop", async () => {
      // Mock sensor readings
      mockServices.sensorData.getSensorReading
        .mockResolvedValueOnce({
          sensorId: "AWD-SF01",
          type: "water-level",
          value: 10, // Normal level
          timestamp: new Date(),
          unit: "cm",
        })
        .mockResolvedValueOnce({
          sensorId: "MOIST-SF06",
          type: "moisture",
          value: 12, // Normal moisture
          timestamp: new Date(),
          unit: "%",
        });

      // Run control loop
      await controller.runControlLoop();

      // Should process both plots
      expect(mockServices.sensorData.getSensorReading).toHaveBeenCalledTimes(2);
      expect(mockServices.sensorData.getSensorReading).toHaveBeenCalledWith(
        "AWD-SF01",
      );
      expect(mockServices.sensorData.getSensorReading).toHaveBeenCalledWith(
        "MOIST-SF06",
      );
    });

    it("should continue processing even if one plot fails", async () => {
      // Mock sensor readings
      mockServices.sensorData.getSensorReading
        .mockRejectedValueOnce(new Error("Sensor error"))
        .mockResolvedValueOnce({
          sensorId: "MOIST-SF06",
          type: "moisture",
          value: 8,
          timestamp: new Date(),
          unit: "%",
        });

      // Run control loop
      await controller.runControlLoop();

      // Should still process second plot
      expect(mockServices.sensorData.getSensorReading).toHaveBeenCalledTimes(2);
      expect(mockServices.valveCommand.sendValveCommand).toHaveBeenCalledWith(
        "SF06",
        1,
        expect.any(Date),
        expect.any(String),
      );
    });

    it("should handle concurrent AWD plots with different thresholds without interference", async () => {
      // Add third plot with different AWD thresholds
      const plot3Config = {
        plotId: "SF10",
        areaRai: 3.0,
        sensorId: "AWD-SF10",
        valveName: "SV_SF10",
        cropType: "rice",
      };

      // Mock control mode for third plot
      mockServices.controlMode.getMode.mockImplementation((plotId) => {
        if (plotId === "SF01" || plotId === "SF10") return "AWD";
        if (plotId === "SF06") return "MOISTURE";
        throw new Error(`No control mode configured for plot: ${plotId}`);
      });

      // Mock different thresholds for each AWD plot
      const originalGetControlThresholds =
        mockServices.timescaleRepository.getControlThresholds;
      mockServices.timescaleRepository.getControlThresholds = jest.fn(
        (db, plotId) => {
          if (plotId === "SF01") {
            return Promise.resolve({
              plotId: "SF01",
              moistureLowerThreshold: 10,
              moistureUpperThreshold: 15,
              waterLevelLowerThreshold: 5,
              waterLevelUpperThreshold: 15,
            });
          }
          if (plotId === "SF10") {
            return Promise.resolve({
              plotId: "SF10",
              moistureLowerThreshold: 10,
              moistureUpperThreshold: 15,
              waterLevelLowerThreshold: 3,
              waterLevelUpperThreshold: 20,
            });
          }
          return originalGetControlThresholds(db, plotId);
        },
      );

      // Mock sensor readings - both at same water level (7cm)
      mockServices.sensorData.getSensorReading
        .mockResolvedValueOnce({
          sensorId: "AWD-SF01",
          type: "water-level",
          value: 7,
          timestamp: new Date(),
          unit: "cm",
        })
        .mockResolvedValueOnce({
          sensorId: "AWD-SF10",
          type: "water-level",
          value: 7,
          timestamp: new Date(),
          unit: "cm",
        });

      // Process both plots
      const decision1 = await controller.processPlot(mockConfig.plots[0]);
      const decision2 = await controller.processPlot(plot3Config);

      // SF01: 7cm > 5cm (min) and < 15cm (max) = MAINTAIN
      expect(decision1.action).toBe("MAINTAIN");
      expect(decision1.thresholds.min).toBe(5);
      expect(decision1.thresholds.max).toBe(15);

      // SF10: 7cm > 3cm (min) and < 20cm (max) = MAINTAIN
      expect(decision2.action).toBe("MAINTAIN");
      expect(decision2.thresholds.min).toBe(3);
      expect(decision2.thresholds.max).toBe(20);

      // Verify no state bleeding - each plot used its own thresholds
      expect(
        mockServices.timescaleRepository.getControlThresholds,
      ).toHaveBeenCalledTimes(2);
    });
  });
});
