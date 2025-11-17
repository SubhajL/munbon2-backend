const { describe, test, expect, beforeEach } = require('@jest/globals');

describe('GeoSpatialSensorResolver', () => {
  let resolver;
  let mockRepository;
  let mockLogger;

  beforeEach(() => {
    mockRepository = {
      findPlotByCoordinates: jest.fn(),
      upsertSensorPlotMapping: jest.fn(),
      getSensorPlotMapping: jest.fn(),
      pool: {}
    };

    mockLogger = {
      info: jest.fn(),
      warn: jest.fn(),
      error: jest.fn(),
      debug: jest.fn()
    };
  });

  describe('resolvePlotFromCoordinates', () => {
    test('returns plot ID when point inside polygon', async () => {
      const GeoSpatialSensorResolver = require('../geoSpatialSensorResolver');

      mockRepository.findPlotByCoordinates = jest
        .fn()
        .mockResolvedValue('SF-L1');

      resolver = new GeoSpatialSensorResolver({
        repository: mockRepository,
        logger: mockLogger
      });

      const plotId = await resolver.resolvePlotFromCoordinates(
        102.15075,
        14.49655,
        'water_level'
      );

      expect(plotId).toBe('SF-L1');
      expect(mockRepository.findPlotByCoordinates).toHaveBeenCalledWith(
        expect.any(Object),
        102.15075,
        14.49655
      );
    });

    test('returns null when point outside all plots', async () => {
      const GeoSpatialSensorResolver = require('../geoSpatialSensorResolver');

      mockRepository.findPlotByCoordinates = jest.fn().mockResolvedValue(null);

      resolver = new GeoSpatialSensorResolver({
        repository: mockRepository,
        logger: mockLogger
      });

      const plotId = await resolver.resolvePlotFromCoordinates(
        0,
        0,
        'water_level'
      );

      expect(plotId).toBeNull();
    });

    test('returns null for invalid coordinates', async () => {
      const GeoSpatialSensorResolver = require('../geoSpatialSensorResolver');

      resolver = new GeoSpatialSensorResolver({
        repository: mockRepository,
        logger: mockLogger
      });

      expect(await resolver.resolvePlotFromCoordinates(null, 14.5, 'water_level')).toBeNull();
      expect(await resolver.resolvePlotFromCoordinates(102.1, null, 'water_level')).toBeNull();
      expect(await resolver.resolvePlotFromCoordinates(undefined, undefined, 'water_level')).toBeNull();
    });
  });

  describe('ensureSensorMapping', () => {
    test('creates new mapping when none exists', async () => {
      const GeoSpatialSensorResolver = require('../geoSpatialSensorResolver');

      mockRepository.getSensorPlotMapping = jest.fn().mockResolvedValue(null);
      mockRepository.upsertSensorPlotMapping = jest
        .fn()
        .mockResolvedValue('SF-L1');

      resolver = new GeoSpatialSensorResolver({
        repository: mockRepository,
        logger: mockLogger
      });

      const result = await resolver.ensureSensorMapping(
        'AWD-A4F8',
        'SF-L1',
        'water_level'
      );

      expect(result).toEqual({
        plotId: 'SF-L1',
        wasCreated: true,
        previousPlotId: null
      });

      expect(mockRepository.upsertSensorPlotMapping).toHaveBeenCalledWith(
        expect.any(Object),
        {
          sensorId: 'AWD-A4F8',
          plotId: 'SF-L1',
          sensorType: 'water_level'
        }
      );
    });

    test('updates existing mapping when plot changes', async () => {
      const GeoSpatialSensorResolver = require('../geoSpatialSensorResolver');

      mockRepository.getSensorPlotMapping = jest.fn().mockResolvedValue({
        plotId: 'SF-L1',
        sensorType: 'water_level'
      });

      mockRepository.upsertSensorPlotMapping = jest
        .fn()
        .mockResolvedValue('SF-L2');

      resolver = new GeoSpatialSensorResolver({
        repository: mockRepository,
        logger: mockLogger
      });

      const result = await resolver.ensureSensorMapping(
        'AWD-A4F8',
        'SF-L2',
        'water_level'
      );

      expect(result).toEqual({
        plotId: 'SF-L2',
        wasCreated: false,
        previousPlotId: 'SF-L1'
      });
    });

    test('returns existing mapping when plot unchanged', async () => {
      const GeoSpatialSensorResolver = require('../geoSpatialSensorResolver');

      mockRepository.getSensorPlotMapping = jest.fn().mockResolvedValue({
        plotId: 'SF-L1',
        sensorType: 'water_level'
      });

      mockRepository.upsertSensorPlotMapping = jest.fn();

      resolver = new GeoSpatialSensorResolver({
        repository: mockRepository,
        logger: mockLogger
      });

      const result = await resolver.ensureSensorMapping(
        'AWD-A4F8',
        'SF-L1',
        'water_level'
      );

      expect(result).toEqual({
        plotId: 'SF-L1',
        wasCreated: false,
        previousPlotId: null
      });

      expect(mockRepository.upsertSensorPlotMapping).not.toHaveBeenCalled();
    });
  });

  describe('resolveAndMapSensor', () => {
    test('orchestrates full flow for new sensor', async () => {
      const GeoSpatialSensorResolver = require('../geoSpatialSensorResolver');

      mockRepository.findPlotByCoordinates = jest
        .fn()
        .mockResolvedValue('SF-L2');
      mockRepository.getSensorPlotMapping = jest.fn().mockResolvedValue(null);
      mockRepository.upsertSensorPlotMapping = jest
        .fn()
        .mockResolvedValue('SF-L2');

      resolver = new GeoSpatialSensorResolver({
        repository: mockRepository,
        logger: mockLogger
      });

      const result = await resolver.resolveAndMapSensor({
        sensorId: 'AWD-A4F8',
        longitude: 102.15075,
        latitude: 14.49655,
        sensorType: 'water_level'
      });

      expect(result).toEqual({
        plotId: 'SF-L2',
        sensorId: 'AWD-A4F8',
        sensorType: 'water_level',
        wasCreated: true,
        previousPlotId: null
      });
    });

    test('returns null when coordinates invalid', async () => {
      const GeoSpatialSensorResolver = require('../geoSpatialSensorResolver');

      resolver = new GeoSpatialSensorResolver({
        repository: mockRepository,
        logger: mockLogger
      });

      const result = await resolver.resolveAndMapSensor({
        sensorId: 'AWD-A4F8',
        longitude: null,
        latitude: 14.5,
        sensorType: 'water_level'
      });

      expect(result).toBeNull();
    });

    test('returns null when plot not found', async () => {
      const GeoSpatialSensorResolver = require('../geoSpatialSensorResolver');

      mockRepository.findPlotByCoordinates = jest.fn().mockResolvedValue(null);

      resolver = new GeoSpatialSensorResolver({
        repository: mockRepository,
        logger: mockLogger
      });

      const result = await resolver.resolveAndMapSensor({
        sensorId: 'AWD-A4F8',
        longitude: 0,
        latitude: 0,
        sensorType: 'water_level'
      });

      expect(result).toBeNull();
    });

    test('skips mapping when auto-mapping disabled', async () => {
      const GeoSpatialSensorResolver = require('../geoSpatialSensorResolver');

      mockRepository.findPlotByCoordinates = jest
        .fn()
        .mockResolvedValue('SF-L2');
      mockRepository.upsertSensorPlotMapping = jest.fn();

      resolver = new GeoSpatialSensorResolver({
        repository: mockRepository,
        logger: mockLogger,
        enableAutoMapping: false
      });

      const result = await resolver.resolveAndMapSensor({
        sensorId: 'AWD-A4F8',
        longitude: 102.15075,
        latitude: 14.49655,
        sensorType: 'water_level'
      });

      expect(result).toEqual({
        plotId: 'SF-L2',
        sensorId: 'AWD-A4F8',
        sensorType: 'water_level',
        wasCreated: false,
        previousPlotId: null
      });

      expect(mockRepository.upsertSensorPlotMapping).not.toHaveBeenCalled();
    });
  });
});
