# LinuxCNC Hardware Drivers 

> LinuxCNC is not a CNC program.  
> It is a **real-time hardware control operating system**.

Its only real job is to convert **motion math** into **electrical signals** that move motors, and convert **electrical feedback** back into **numbers**.

That job is performed by **hardware drivers**.

---

# 1. The One Control Pipeline

Every LinuxCNC machine, from a hobby mill to an industrial robot, follows exactly the same pipeline:

G-code / GUI
↓
Trajectory Planner (math)
↓
Motion Controller (positions & velocities)
↓
HAL (real-time signal bus)
↓
Hardware Driver
↓
Physical Pins
↓
Motor / Encoder / VFD / Switch


If this pipeline is not understood, LinuxCNC is not understood.

---

# 2. What a Hardware Driver Really Is

A LinuxCNC hardware driver is:

> A **real-time signal translator** that turns software numbers into electricity, and electricity back into numbers.

It converts:

| LinuxCNC produces | Hardware needs |
|------------------|----------------|
| Position numbers | Step pulses |
| Velocity numbers | PWM |
| Enable bits | Logic voltages |
| Encoder counts | Feedback numbers |

This is where **software touches physics**.

---

# 3. Why HAL Exists

LinuxCNC does not allow motion control to talk directly to hardware.

Instead it uses:

Motion → HAL → Driver → Hardware


HAL is a **real-time signal bus** — similar in concept to PCI, CAN, or EtherCAT.

Drivers connect to HAL using:
- Pins
- Signals
- Realtime threads

This makes LinuxCNC:
- Hardware-independent
- Debuggable
- Modular
- Industrial-grade

---

# 4. The Two Classes of Hardware Drivers

All LinuxCNC drivers fall into one of two categories.

---

## A) CPU-Driven Drivers (software timing)

Examples:
- Parallel port
- Raspberry Pi GPIO
- `mb2hal` (Modbus)

Here:

Linux CPU
├─ Generates step pulses
├─ Samples encoders
└─ Toggles pins


**Pros**
- Cheap
- Simple
- Flexible

**Cons**
- Jitter
- Speed limits
- Not industrial-grade

Used for:
- Hobby CNC
- Low-cost controllers
- Non-critical automation

---

## B) Hardware-Offloaded Drivers (FPGA / smart I/O)

Examples:
- Mesa (HostMot2)
- EtherCAT drives
- Industrial servo controllers

Here:

LinuxCNC → sends numbers
Hardware → generates electrical waveforms


The hardware handles:
- Step pulses
- Encoder counting
- PWM
- DAC
- Limit switches

LinuxCNC only streams:
- Position
- Velocity
- Enable

This is how **real CNC controllers** work.

---

# 5. Mesa & HostMot2 — The Industrial Core

Mesa cards contain an FPGA running **HostMot2 firmware**.

Architecture:

LinuxCNC
↓
hostmot2 driver
↓
PCI / Ethernet
↓
Mesa FPGA
↓
Stepgen / Encoder / PWM logic
↓
Physical pins


LinuxCNC never touches the pins directly.  
The FPGA performs all real-time electrical control.

This is why Mesa behaves like Fanuc, Siemens, or Heidenhain.

---

# 6. Canonical Device Interface (Hardware API)

LinuxCNC forces all hardware to expose the same HAL pins.

| Function | HAL Pin |
|--------|--------|
| Stepper | `stepgen.N` |
| Encoder | `encoder.N` |
| Digital input | `motion.digital-in-N` |
| Analog output | `motion.analog-out-N` |

This means:
- Motion control does not know what hardware is used
- HAL wiring stays the same
- Hardware can be swapped without rewriting logic

This is LinuxCNC’s **hardware abstraction layer**.

---

# 7. What Really Happens When an Axis Moves

Example: X-axis move

G1 X100
↓
Trajectory planner computes path
↓
motion.position-cmd
↓
stepgen.0.position-cmd
↓
Driver (Mesa or GPIO)
↓
Electrical pulses
↓
Motor driver
↓
Motor rotates


Feedback loop:

Encoder → Driver → encoder.0.position → motion.position-fb


This is a closed-loop real-time control system.

---



LinuxCNC hardware drivers are:
- Realtime
- Deterministic
- Shared-memory based
- Hardware-abstracted
- Control-loop driven