# What LinuxCNC is

LinuxCNC is not a G-code player.
It is a real-time motion control system.

It consists of:
- A trajectory planner
- A real-time servo loop
- Hardware drivers
- A signal routing system (HAL)
- A GUI

The GUI never controls motors directly.
All motion is executed by the real-time motion controller.
