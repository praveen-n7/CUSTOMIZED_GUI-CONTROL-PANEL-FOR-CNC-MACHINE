# HAL (Hardware Abstraction Layer)

HAL is LinuxCNC’s real-time signal routing system.

It connects:
Motion controller
→ PID
→ Step generators
→ Hardware drivers
→ Feedback (encoders, switches)

HAL consists of:
- Pins (inputs & outputs)
- Signals (wires)
- Parameters (tuning values)
- Threads (timing)

HAL is what turns LinuxCNC from software into a machine.
