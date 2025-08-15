-- Gravity Optimizer Real Network Data Migration
-- Generated from Flow Monitoring Service data
-- Date: 2025-08-14T07:39:02.294177

BEGIN;

-- Clear existing test data
TRUNCATE gravity.hydraulic_nodes CASCADE;
TRUNCATE gravity.channels CASCADE;
TRUNCATE gravity.gates CASCADE;
TRUNCATE gravity.zones CASCADE;

-- Insert hydraulic nodes
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('source', 'Main Reservoir', 221.00, ST_SetSRID(ST_MakePoint(101.0, 14.0), 4326), 0.0000, 1);
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('M(0,0)', 'Outlet Gate M(0,0)', 218.00, ST_SetSRID(ST_MakePoint(101.0, 14.01), 4326), 0.0000, 2);
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('M(0,1)', 'LMC Gate M(0,1)', 217.90, ST_SetSRID(ST_MakePoint(101.001, 14.0), 4326), 0.0000, 1);
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('M(0,2)', 'LMC Gate M(0,2)', 217.90, ST_SetSRID(ST_MakePoint(101.002, 14.01), 4326), 0.0000, 2);
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('M(0,3)', 'LMC Gate M(0,3)', 217.80, ST_SetSRID(ST_MakePoint(101.003, 14.01), 4326), 0.0000, 2);
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('M(0,4)', 'LMC Gate M(0,4)', 216.00, ST_SetSRID(ST_MakePoint(101.004, 14.01), 4326), 0.0000, 2);
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('M(0,5)', 'LMC Gate M(0,5)', 217.00, ST_SetSRID(ST_MakePoint(101.005, 14.02), 4326), 0.0000, 3);
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('M(0,6)', 'LMC Gate M(0,6)', 216.00, ST_SetSRID(ST_MakePoint(101.006, 14.02), 4326), 0.0000, 3);
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('M(0,7)', 'LMC Gate M(0,7)', 216.00, ST_SetSRID(ST_MakePoint(101.007, 14.02), 4326), 0.0000, 3);
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('M(0,8)', 'LMC Gate M(0,8)', 216.00, ST_SetSRID(ST_MakePoint(101.008, 14.02), 4326), 0.0000, 3);
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('M(0,9)', 'LMC Gate M(0,9)', 216.00, ST_SetSRID(ST_MakePoint(101.009, 14.02), 4326), 0.0000, 3);
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('M(0,10)', 'LMC Gate M(0,10)', 216.00, ST_SetSRID(ST_MakePoint(101.01, 14.02), 4326), 0.0000, 3);
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('M(0,11)', 'LMC Gate M(0,11)', 216.00, ST_SetSRID(ST_MakePoint(101.011, 14.02), 4326), 0.0000, 3);
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('M(0,12)', 'LMC Gate M(0,12)', 215.00, ST_SetSRID(ST_MakePoint(101.012, 14.02), 4326), 0.0000, 3);
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('M(0,13)', 'LMC Gate M(0,13)', 216.00, ST_SetSRID(ST_MakePoint(101.013, 14.02), 4326), 0.0000, 3);
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('M(0,14)', 'LMC Gate M(0,14)', 214.50, ST_SetSRID(ST_MakePoint(101.014, 14.02), 4326), 0.0000, 3);
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('M(0,0; 1,0)', 'Waste Way Gate M(0,0; 1,0)', 216.00, ST_SetSRID(ST_MakePoint(101.015, 14.01), 4326), 0.0000, 2);
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('M (0,1; 1,0)', 'RMC Gate M (0,1; 1,0)', 216.00, ST_SetSRID(ST_MakePoint(101.017, 14.06), 4326), 0.0000, 5);
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('M (0,1; 1,1)', 'RMC Gate M (0,1; 1,1)', 216.00, ST_SetSRID(ST_MakePoint(101.018, 14.06), 4326), 0.0000, 5);
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('M (0,1; 1,2)', 'RMC Gate M (0,1; 1,2)', 216.00, ST_SetSRID(ST_MakePoint(101.019, 14.06), 4326), 0.0000, 5);
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('M (0,1; 1,3)', 'RMC Gate M (0,1; 1,3)', 216.00, ST_SetSRID(ST_MakePoint(101.02, 14.06), 4326), 0.0000, 5);
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('M (0,1; 1,4)', 'RMC Gate M (0,1; 1,4)', 216.00, ST_SetSRID(ST_MakePoint(101.021, 14.06), 4326), 0.0000, 5);
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('M(0,1; 1,0; 1,0)', 'FTO 2+450 Gate M(0,1; 1,0; 1,0)', 216.00, ST_SetSRID(ST_MakePoint(101.022, 14.06), 4326), 0.0000, 5);
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('M(0,1; 1,1; 1,0)', '4L-RMC Gate M(0,1; 1,1; 1,0)', 216.00, ST_SetSRID(ST_MakePoint(101.024, 14.06), 4326), 0.0000, 5);
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('M(0,1; 1,1; 1,1)', '4L-RMC Gate M(0,1; 1,1; 1,1)', 216.00, ST_SetSRID(ST_MakePoint(101.025, 14.06), 4326), 0.0000, 5);
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('M(0,1; 1,1; 1,2)', '4L-RMC Gate M(0,1; 1,1; 1,2)', 216.00, ST_SetSRID(ST_MakePoint(101.026, 14.06), 4326), 0.0000, 5);
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('M(0,1; 1,1; 1,3)', '4L-RMC Gate M(0,1; 1,1; 1,3)', 216.00, ST_SetSRID(ST_MakePoint(101.027, 14.06), 4326), 0.0000, 5);
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('M(0,1; 1,1; 1,4)', '4L-RMC Gate M(0,1; 1,1; 1,4)', 216.00, ST_SetSRID(ST_MakePoint(101.028, 14.06), 4326), 0.0000, 5);
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('M(0,1; 1,1; 1,2; 1,0)', 'FTO337 Rai Gate M(0,1; 1,1; 1,2; 1,0)', 216.00, ST_SetSRID(ST_MakePoint(101.029, 14.06), 4326), 0.0000, 5);
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('M (0,3; 1,0)', '9R-LMC Gate M (0,3; 1,0)', 216.00, ST_SetSRID(ST_MakePoint(101.031, 14.03), 4326), 0.0000, 4);
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('M (0,3; 1,1)', '9R-LMC Gate M (0,3; 1,1)', 216.00, ST_SetSRID(ST_MakePoint(101.032, 14.03), 4326), 0.0000, 4);
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('M (0,3; 1,2)', '9R-LMC Gate M (0,3; 1,2)', 216.00, ST_SetSRID(ST_MakePoint(101.033, 14.03), 4326), 0.0000, 4);
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('M (0,3; 1,3)', '9R-LMC Gate M (0,3; 1,3)', 216.00, ST_SetSRID(ST_MakePoint(101.034, 14.03), 4326), 0.0000, 4);
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('M (0,3; 1,1; 1,0)', '7R-9R-LMC Gate M (0,3; 1,1; 1,0)', 216.00, ST_SetSRID(ST_MakePoint(101.035, 14.03), 4326), 0.0000, 4);
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('M (0,3; 1,1; 1,1)', '7R-9R-LMC Gate M (0,3; 1,1; 1,1)', 216.00, ST_SetSRID(ST_MakePoint(101.036, 14.03), 4326), 0.0000, 4);
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('M (0,3; 1,1; 2,0)', '7L-9R-LMC Gate M (0,3; 1,1; 2,0)', 216.00, ST_SetSRID(ST_MakePoint(101.037, 14.03), 4326), 0.0000, 4);
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('M (0,3; 1,1; 2,1)', '7L-9R-LMC Gate M (0,3; 1,1; 2,1)', 216.00, ST_SetSRID(ST_MakePoint(101.038, 14.03), 4326), 0.0000, 4);
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('M (0,12; 1,0)', '38R-LMC Gate M (0,12; 1,0)', 216.00, ST_SetSRID(ST_MakePoint(101.04, 14.04), 4326), 0.0000, 5);
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('M (0,12; 1,1)', '38R-LMC Gate M (0,12; 1,1)', 216.00, ST_SetSRID(ST_MakePoint(101.041, 14.04), 4326), 0.0000, 5);
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('M (0,12; 1,2)', '38R-LMC Gate M (0,12; 1,2)', 216.00, ST_SetSRID(ST_MakePoint(101.042, 14.04), 4326), 0.0000, 5);
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('M (0,12; 1,3)', '38R-LMC Gate M (0,12; 1,3)', 216.00, ST_SetSRID(ST_MakePoint(101.043, 14.05), 4326), 0.0000, 5);
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('M (0,12; 1,4)', '38R-LMC Gate M (0,12; 1,4)', 216.00, ST_SetSRID(ST_MakePoint(101.044, 14.05), 4326), 0.0000, 5);
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('M (0,12; 1,5)', '38R-LMC Gate M (0,12; 1,5)', 216.00, ST_SetSRID(ST_MakePoint(101.045, 14.05), 4326), 0.0000, 5);
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('M (0,12; 1,0; 1,0)', '1R-38R-LMC Gate M (0,12; 1,0; 1,0)', 216.00, ST_SetSRID(ST_MakePoint(101.046, 14.04), 4326), 0.0000, 5);
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('M (0,12; 1,0; 1,1)', '1R-38R-LMC Gate M (0,12; 1,0; 1,1)', 216.00, ST_SetSRID(ST_MakePoint(101.047, 14.04), 4326), 0.0000, 5);
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('M (0,12; 1,1; 1,0)', '2R-38R-LMC Gate M (0,12; 1,1; 1,0)', 216.00, ST_SetSRID(ST_MakePoint(101.048, 14.04), 4326), 0.0000, 5);
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('M (0,12; 1,1; 1,1)', '2R-38R-LMC Gate M (0,12; 1,1; 1,1)', 216.00, ST_SetSRID(ST_MakePoint(101.049, 14.04), 4326), 0.0000, 5);
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('M (0,12; 1,1; 1,2)', '2R-38R-LMC Gate M (0,12; 1,1; 1,2)', 216.00, ST_SetSRID(ST_MakePoint(101.05, 14.04), 4326), 0.0000, 5);
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('M (0,12; 1,1; 1,0; 1,0)', '1R-2R-38R-LMC Gate M (0,12; 1,1; 1,0; 1,0)', 216.00, ST_SetSRID(ST_MakePoint(101.051, 14.04), 4326), 0.0000, 5);
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('M (0,12; 1,1; 1,0; 1,1)', '1R-2R-38R-LMC Gate M (0,12; 1,1; 1,0; 1,1)', 216.00, ST_SetSRID(ST_MakePoint(101.052, 14.04), 4326), 0.0000, 5);
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('M (0,12; 1,1; 1,0; 1,2)', '1R-2R-38R-LMC Gate M (0,12; 1,1; 1,0; 1,2)', 216.00, ST_SetSRID(ST_MakePoint(101.053, 14.04), 4326), 0.0000, 5);
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('M (0,12; 1,2; 1,0)', '4L-38R-LMC Gate M (0,12; 1,2; 1,0)', 216.00, ST_SetSRID(ST_MakePoint(101.054, 14.05), 4326), 0.0000, 5);
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('M (0,12; 1,2; 1,1)', '4L-38R-LMC Gate M (0,12; 1,2; 1,1)', 216.00, ST_SetSRID(ST_MakePoint(101.055, 14.05), 4326), 0.0000, 5);
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('M (0,12; 1,2; 1,2)', '4L-38R-LMC Gate M (0,12; 1,2; 1,2)', 216.00, ST_SetSRID(ST_MakePoint(101.056, 14.05), 4326), 0.0000, 5);
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('M (0,12; 1,2; 1,0; 1,0)', '5R-4L-38R-LMC Gate M (0,12; 1,2; 1,0; 1,0)', 216.00, ST_SetSRID(ST_MakePoint(101.057, 14.05), 4326), 0.0000, 5);
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('M (0,12; 1,2; 1,0; 1,1)', '5R-4L-38R-LMC Gate M (0,12; 1,2; 1,0; 1,1)', 216.00, ST_SetSRID(ST_MakePoint(101.058, 14.05), 4326), 0.0000, 5);
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('M (0,12; 1,3; 1,0)', '6R-38R-LMC Gate M (0,12; 1,3; 1,0)', 216.00, ST_SetSRID(ST_MakePoint(101.059, 14.05), 4326), 0.0000, 5);
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('M (0,12; 1,3; 1,1)', '6R-38R-LMC Gate M (0,12; 1,3; 1,1)', 216.00, ST_SetSRID(ST_MakePoint(101.06, 14.05), 4326), 0.0000, 5);
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('M (0,12; 1,4; 1,0)', '8R-38R-LMC Gate M (0,12; 1,4; 1,0)', 216.00, ST_SetSRID(ST_MakePoint(101.061, 14.05), 4326), 0.0000, 5);
INSERT INTO gravity.hydraulic_nodes (node_id, name, elevation, location, water_demand, priority) VALUES ('M (0,12; 1,4; 1,1)', '8R-38R-LMC Gate M (0,12; 1,4; 1,1)', 216.00, ST_SetSRID(ST_MakePoint(101.062, 14.05), 4326), 0.0000, 5);

-- Insert channels

-- Insert gates
INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) VALUES ('M(0,0)', 'manual', ST_SetSRID(ST_MakePoint(101.0, 14.01), 4326), 218.00, 1.0, 0.0);
INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) VALUES ('M(0,1)', 'manual', ST_SetSRID(ST_MakePoint(101.001, 14.0), 4326), 217.90, 1.0, 0.0);
INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) VALUES ('M(0,2)', 'manual', ST_SetSRID(ST_MakePoint(101.002, 14.01), 4326), 217.90, 1.0, 0.0);
INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) VALUES ('M(0,3)', 'manual', ST_SetSRID(ST_MakePoint(101.003, 14.01), 4326), 217.80, 1.0, 0.0);
INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) VALUES ('M(0,4)', 'manual', ST_SetSRID(ST_MakePoint(101.004, 14.01), 4326), 216.00, 1.0, 0.0);
INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) VALUES ('M(0,5)', 'manual', ST_SetSRID(ST_MakePoint(101.005, 14.02), 4326), 217.00, 1.0, 0.0);
INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) VALUES ('M(0,6)', 'manual', ST_SetSRID(ST_MakePoint(101.006, 14.02), 4326), 216.00, 1.0, 0.0);
INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) VALUES ('M(0,7)', 'manual', ST_SetSRID(ST_MakePoint(101.007, 14.02), 4326), 216.00, 1.0, 0.0);
INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) VALUES ('M(0,8)', 'manual', ST_SetSRID(ST_MakePoint(101.008, 14.02), 4326), 216.00, 1.0, 0.0);
INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) VALUES ('M(0,9)', 'manual', ST_SetSRID(ST_MakePoint(101.009, 14.02), 4326), 216.00, 1.0, 0.0);
INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) VALUES ('M(0,10)', 'manual', ST_SetSRID(ST_MakePoint(101.01, 14.02), 4326), 216.00, 1.0, 0.0);
INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) VALUES ('M(0,11)', 'manual', ST_SetSRID(ST_MakePoint(101.011, 14.02), 4326), 216.00, 1.0, 0.0);
INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) VALUES ('M(0,12)', 'manual', ST_SetSRID(ST_MakePoint(101.012, 14.02), 4326), 215.00, 1.0, 0.0);
INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) VALUES ('M(0,13)', 'manual', ST_SetSRID(ST_MakePoint(101.013, 14.02), 4326), 216.00, 1.0, 0.0);
INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) VALUES ('M(0,14)', 'manual', ST_SetSRID(ST_MakePoint(101.014, 14.02), 4326), 214.50, 1.0, 0.0);
INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) VALUES ('M(0,0; 1,0)', 'manual', ST_SetSRID(ST_MakePoint(101.015, 14.01), 4326), 216.00, 1.0, 0.0);
INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) VALUES ('M (0,1; 1,0)', 'manual', ST_SetSRID(ST_MakePoint(101.017, 14.06), 4326), 216.00, 1.0, 0.0);
INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) VALUES ('M (0,1; 1,1)', 'manual', ST_SetSRID(ST_MakePoint(101.018, 14.06), 4326), 216.00, 1.0, 0.0);
INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) VALUES ('M (0,1; 1,2)', 'manual', ST_SetSRID(ST_MakePoint(101.019, 14.06), 4326), 216.00, 1.0, 0.0);
INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) VALUES ('M (0,1; 1,3)', 'manual', ST_SetSRID(ST_MakePoint(101.02, 14.06), 4326), 216.00, 1.0, 0.0);
INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) VALUES ('M (0,1; 1,4)', 'manual', ST_SetSRID(ST_MakePoint(101.021, 14.06), 4326), 216.00, 1.0, 0.0);
INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) VALUES ('M(0,1; 1,0; 1,0)', 'manual', ST_SetSRID(ST_MakePoint(101.022, 14.06), 4326), 216.00, 1.0, 0.0);
INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) VALUES ('M(0,1; 1,1; 1,0)', 'manual', ST_SetSRID(ST_MakePoint(101.024, 14.06), 4326), 216.00, 1.0, 0.0);
INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) VALUES ('M(0,1; 1,1; 1,1)', 'manual', ST_SetSRID(ST_MakePoint(101.025, 14.06), 4326), 216.00, 1.0, 0.0);
INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) VALUES ('M(0,1; 1,1; 1,2)', 'manual', ST_SetSRID(ST_MakePoint(101.026, 14.06), 4326), 216.00, 1.0, 0.0);
INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) VALUES ('M(0,1; 1,1; 1,3)', 'manual', ST_SetSRID(ST_MakePoint(101.027, 14.06), 4326), 216.00, 1.0, 0.0);
INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) VALUES ('M(0,1; 1,1; 1,4)', 'manual', ST_SetSRID(ST_MakePoint(101.028, 14.06), 4326), 216.00, 1.0, 0.0);
INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) VALUES ('M(0,1; 1,1; 1,2; 1,0)', 'manual', ST_SetSRID(ST_MakePoint(101.029, 14.06), 4326), 216.00, 1.0, 0.0);
INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) VALUES ('M (0,3; 1,0)', 'manual', ST_SetSRID(ST_MakePoint(101.031, 14.03), 4326), 216.00, 1.0, 0.0);
INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) VALUES ('M (0,3; 1,1)', 'manual', ST_SetSRID(ST_MakePoint(101.032, 14.03), 4326), 216.00, 1.0, 0.0);
INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) VALUES ('M (0,3; 1,2)', 'manual', ST_SetSRID(ST_MakePoint(101.033, 14.03), 4326), 216.00, 1.0, 0.0);
INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) VALUES ('M (0,3; 1,3)', 'manual', ST_SetSRID(ST_MakePoint(101.034, 14.03), 4326), 216.00, 1.0, 0.0);
INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) VALUES ('M (0,3; 1,1; 1,0)', 'manual', ST_SetSRID(ST_MakePoint(101.035, 14.03), 4326), 216.00, 1.0, 0.0);
INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) VALUES ('M (0,3; 1,1; 1,1)', 'manual', ST_SetSRID(ST_MakePoint(101.036, 14.03), 4326), 216.00, 1.0, 0.0);
INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) VALUES ('M (0,3; 1,1; 2,0)', 'manual', ST_SetSRID(ST_MakePoint(101.037, 14.03), 4326), 216.00, 1.0, 0.0);
INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) VALUES ('M (0,3; 1,1; 2,1)', 'manual', ST_SetSRID(ST_MakePoint(101.038, 14.03), 4326), 216.00, 1.0, 0.0);
INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) VALUES ('M (0,12; 1,0)', 'automated', ST_SetSRID(ST_MakePoint(101.04, 14.04), 4326), 216.00, 1.0, 0.0);
INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) VALUES ('M (0,12; 1,1)', 'automated', ST_SetSRID(ST_MakePoint(101.041, 14.04), 4326), 216.00, 1.0, 0.0);
INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) VALUES ('M (0,12; 1,2)', 'automated', ST_SetSRID(ST_MakePoint(101.042, 14.04), 4326), 216.00, 1.0, 0.0);
INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) VALUES ('M (0,12; 1,3)', 'automated', ST_SetSRID(ST_MakePoint(101.043, 14.05), 4326), 216.00, 1.0, 0.0);
INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) VALUES ('M (0,12; 1,4)', 'automated', ST_SetSRID(ST_MakePoint(101.044, 14.05), 4326), 216.00, 1.0, 0.0);
INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) VALUES ('M (0,12; 1,5)', 'manual', ST_SetSRID(ST_MakePoint(101.045, 14.05), 4326), 216.00, 1.0, 0.0);
INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) VALUES ('M (0,12; 1,0; 1,0)', 'automated', ST_SetSRID(ST_MakePoint(101.046, 14.04), 4326), 216.00, 1.0, 0.0);
INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) VALUES ('M (0,12; 1,0; 1,1)', 'automated', ST_SetSRID(ST_MakePoint(101.047, 14.04), 4326), 216.00, 1.0, 0.0);
INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) VALUES ('M (0,12; 1,1; 1,0)', 'automated', ST_SetSRID(ST_MakePoint(101.048, 14.04), 4326), 216.00, 1.0, 0.0);
INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) VALUES ('M (0,12; 1,1; 1,1)', 'automated', ST_SetSRID(ST_MakePoint(101.049, 14.04), 4326), 216.00, 1.0, 0.0);
INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) VALUES ('M (0,12; 1,1; 1,2)', 'automated', ST_SetSRID(ST_MakePoint(101.05, 14.04), 4326), 216.00, 1.0, 0.0);
INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) VALUES ('M (0,12; 1,1; 1,0; 1,0)', 'automated', ST_SetSRID(ST_MakePoint(101.051, 14.04), 4326), 216.00, 1.0, 0.0);
INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) VALUES ('M (0,12; 1,1; 1,0; 1,1)', 'automated', ST_SetSRID(ST_MakePoint(101.052, 14.04), 4326), 216.00, 1.0, 0.0);
INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) VALUES ('M (0,12; 1,1; 1,0; 1,2)', 'automated', ST_SetSRID(ST_MakePoint(101.053, 14.04), 4326), 216.00, 1.0, 0.0);
INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) VALUES ('M (0,12; 1,2; 1,0)', 'automated', ST_SetSRID(ST_MakePoint(101.054, 14.05), 4326), 216.00, 1.0, 0.0);
INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) VALUES ('M (0,12; 1,2; 1,1)', 'automated', ST_SetSRID(ST_MakePoint(101.055, 14.05), 4326), 216.00, 1.0, 0.0);
INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) VALUES ('M (0,12; 1,2; 1,2)', 'automated', ST_SetSRID(ST_MakePoint(101.056, 14.05), 4326), 216.00, 1.0, 0.0);
INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) VALUES ('M (0,12; 1,2; 1,0; 1,0)', 'automated', ST_SetSRID(ST_MakePoint(101.057, 14.05), 4326), 216.00, 1.0, 0.0);
INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) VALUES ('M (0,12; 1,2; 1,0; 1,1)', 'automated', ST_SetSRID(ST_MakePoint(101.058, 14.05), 4326), 216.00, 1.0, 0.0);
INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) VALUES ('M (0,12; 1,3; 1,0)', 'automated', ST_SetSRID(ST_MakePoint(101.059, 14.05), 4326), 216.00, 1.0, 0.0);
INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) VALUES ('M (0,12; 1,3; 1,1)', 'automated', ST_SetSRID(ST_MakePoint(101.06, 14.05), 4326), 216.00, 1.0, 0.0);
INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) VALUES ('M (0,12; 1,4; 1,0)', 'manual', ST_SetSRID(ST_MakePoint(101.061, 14.05), 4326), 216.00, 1.0, 0.0);
INSERT INTO gravity.gates (gate_id, gate_type, location, elevation, max_opening, current_opening) VALUES ('M (0,12; 1,4; 1,1)', 'manual', ST_SetSRID(ST_MakePoint(101.062, 14.05), 4326), 216.00, 1.0, 0.0);

-- Insert zones
INSERT INTO gravity.zones (zone_id, name, min_elevation, max_elevation, area_hectares, boundary) VALUES ('zone_1', 'Irrigation Zone 1', 216.80, 218.00, 2000, ST_SetSRID(ST_MakePolygon(ST_MakeLine(ARRAY[ST_MakePoint(101.0, 14.0), ST_MakePoint(101.1, 14.0), ST_MakePoint(101.1, 14.1), ST_MakePoint(101.0, 14.1), ST_MakePoint(101.0, 14.0)])), 4326));
INSERT INTO gravity.zones (zone_id, name, min_elevation, max_elevation, area_hectares, boundary) VALUES ('zone_2', 'Irrigation Zone 2', 216.00, 217.00, 3000, ST_SetSRID(ST_MakePolygon(ST_MakeLine(ARRAY[ST_MakePoint(101.0, 14.0), ST_MakePoint(101.1, 14.0), ST_MakePoint(101.1, 14.1), ST_MakePoint(101.0, 14.1), ST_MakePoint(101.0, 14.0)])), 4326));
INSERT INTO gravity.zones (zone_id, name, min_elevation, max_elevation, area_hectares, boundary) VALUES ('zone_3', 'Irrigation Zone 3', 214.00, 215.00, 1500, ST_SetSRID(ST_MakePolygon(ST_MakeLine(ARRAY[ST_MakePoint(101.0, 14.0), ST_MakePoint(101.1, 14.0), ST_MakePoint(101.1, 14.1), ST_MakePoint(101.0, 14.1), ST_MakePoint(101.0, 14.0)])), 4326));
INSERT INTO gravity.zones (zone_id, name, min_elevation, max_elevation, area_hectares, boundary) VALUES ('zone_4', 'Irrigation Zone 4', 213.50, 214.50, 1500, ST_SetSRID(ST_MakePolygon(ST_MakeLine(ARRAY[ST_MakePoint(101.0, 14.0), ST_MakePoint(101.1, 14.0), ST_MakePoint(101.1, 14.1), ST_MakePoint(101.0, 14.1), ST_MakePoint(101.0, 14.0)])), 4326));
INSERT INTO gravity.zones (zone_id, name, min_elevation, max_elevation, area_hectares, boundary) VALUES ('zone_5', 'Irrigation Zone 5', 215.50, 216.50, 1500, ST_SetSRID(ST_MakePolygon(ST_MakeLine(ARRAY[ST_MakePoint(101.0, 14.0), ST_MakePoint(101.1, 14.0), ST_MakePoint(101.1, 14.1), ST_MakePoint(101.0, 14.1), ST_MakePoint(101.0, 14.0)])), 4326));
INSERT INTO gravity.zones (zone_id, name, min_elevation, max_elevation, area_hectares, boundary) VALUES ('zone_6', 'Irrigation Zone 6', 215.00, 216.00, 1500, ST_SetSRID(ST_MakePolygon(ST_MakeLine(ARRAY[ST_MakePoint(101.0, 14.0), ST_MakePoint(101.1, 14.0), ST_MakePoint(101.1, 14.1), ST_MakePoint(101.0, 14.1), ST_MakePoint(101.0, 14.0)])), 4326));

COMMIT;