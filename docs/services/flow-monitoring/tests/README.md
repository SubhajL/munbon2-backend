# Flow Monitoring Service - Test Suite

Comprehensive test suite for the Flow Monitoring Service covering unit tests, integration tests, and performance benchmarks.

## Test Structure

```
tests/
├── conftest.py           # Pytest fixtures and configuration
├── pytest.ini            # Pytest settings
├── run_tests.sh          # Test runner script
├── unit/                 # Unit tests
│   ├── test_calibrated_gate_hydraulics.py
│   ├── test_enhanced_hydraulic_solver.py
│   ├── test_gate_registry.py
│   └── test_api_endpoints.py
├── integration/          # Integration tests
│   └── test_mode_transitions.py
└── performance/          # Performance benchmarks
    └── test_benchmarks.py
```

## Running Tests

### Quick Start

```bash
# Run all tests
./tests/run_tests.sh

# Run specific test types
./tests/run_tests.sh unit        # Unit tests only
./tests/run_tests.sh integration # Integration tests only
./tests/run_tests.sh performance # Performance benchmarks
./tests/run_tests.sh coverage    # All tests with coverage report
```

### Using pytest directly

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Run specific test file
pytest tests/unit/test_gate_registry.py

# Run tests matching pattern
pytest tests/ -k "test_hydraulic"

# Run with verbose output
pytest tests/ -v

# Run benchmarks only
pytest tests/performance --benchmark-only
```

## Test Categories

### Unit Tests

**test_calibrated_gate_hydraulics.py**
- Gate flow equation calculations (Q = Cs × L × Hs × √(2g × ΔH))
- Calibration coefficient calculations
- Free/submerged flow detection
- Error handling and edge cases

**test_enhanced_hydraulic_solver.py**
- Network initialization and setup
- Iterative solving convergence
- Mass balance calculations
- Canal flow computations
- Constraint checking (velocity, depth)
- Dual-mode gate handling

**test_gate_registry.py**
- Gate registration and classification
- Mode transition rules
- Equipment status tracking
- Communication failure handling
- Automatic fallback mechanisms

**test_api_endpoints.py**
- All REST API endpoints
- Request/response validation
- Error handling (404, 400, etc.)
- Authentication and authorization
- Mock SCADA/field operations

### Integration Tests

**test_mode_transitions.py**
- AUTO to MANUAL transitions on SCADA failure
- MANUAL to AUTO with safety validation
- Emergency mode transitions
- Gradual transitions during active flow
- State preservation during transitions
- Coordinated multi-gate transitions
- Rollback on failure
- Downstream impact analysis
- Automatic recovery from FAILED state

### Performance Benchmarks

**test_benchmarks.py**
- Hydraulic solver with 50-node network
- Concurrent gate flow calculations (100 gates)
- API throughput (requests/second)
- Memory usage under load
- Solver convergence speed comparison
- Concurrent mode transitions (20 gates)
- State preservation performance
- Mass balance calculation efficiency

## Test Coverage

Target coverage: **80%** minimum

Current coverage areas:
- Core hydraulic calculations: ✓
- Gate control logic: ✓
- API endpoints: ✓
- Mode transitions: ✓
- Error handling: ✓
- Performance optimization: ✓

## Fixtures

Key fixtures available in `conftest.py`:

- `mock_network_config`: Test irrigation network
- `gate_registry`: Pre-configured gate registry
- `calibrated_hydraulics`: Gate hydraulics with calibration
- `mock_db_manager`: Database connection mocks
- `sample_gate_states`: Test gate state data
- `sample_schedule`: Test irrigation schedule
- `test_client`: FastAPI test client

## Performance Benchmarks

Benchmark results include:
- Hydraulic solver iterations and timing
- API request throughput (target: >50 req/s)
- Memory usage (target: <500MB increase)
- Concurrent operation handling
- State preservation speed

## Continuous Integration

Tests are designed to run in CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Run tests
  run: |
    pip install -r requirements.txt
    pytest tests/ --cov=src --cov-report=xml
    
- name: Upload coverage
  uses: codecov/codecov-action@v3
```

## Troubleshooting

### Common Issues

1. **Import errors**: Ensure `src` is in PYTHONPATH
2. **Async test failures**: Check event loop fixture
3. **Performance test variations**: Increase `benchmark_min_rounds`
4. **Coverage gaps**: Run with `--cov-report=html` to identify

### Debug Mode

```bash
# Run with detailed output
pytest tests/ -vv --tb=long

# Run with logging
pytest tests/ --log-cli-level=DEBUG

# Run specific test with breakpoint
pytest tests/unit/test_gate_registry.py::test_update_gate_mode -s
```