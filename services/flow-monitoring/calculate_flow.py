import math

# Test flow calculation with calibration
Cs, L, Hs = 0.85, 3.5, 2.0
g, delta_H = 9.81, 7.0
Q1 = Cs * L * Hs * math.sqrt(2 * g * delta_H)
print(f"With calibration: Q = {Q1:.2f} m³/s")

# Test standard flow equation
Cd, L, Hs = 0.61, 3.5, 2.0
g, delta_H = 9.81, 7.0
Q2 = Cd * L * Hs * math.sqrt(2 * g * delta_H)
print(f"Without calibration: Q = {Q2:.2f} m³/s")