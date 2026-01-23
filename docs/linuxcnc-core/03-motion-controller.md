# Motion controller

LinuxCNC’s motion controller converts G-code into:

- Position commands
- Velocity profiles
- Coordinated multi-axis motion

The motion controller does not talk to hardware.
It outputs signals that are consumed by HAL components like:
- PID
- StepGen
- Servo drives
