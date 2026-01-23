# Real-time execution

LinuxCNC runs a servo loop at a fixed period (typically 1 ms).

Each cycle:
- Trajectory is evaluated
- PID loops run
- Step/velocity commands are generated
- Hardware outputs are updated
- Encoder inputs are read

This loop is deterministic and cannot be delayed by the GUI.
