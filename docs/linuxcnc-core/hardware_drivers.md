HARDWARE DRIVERS


Everything else (GUI, G-code, buttons) is just a skin.

The real job of LinuxCNC is:

Convert motion math into electrical signals that move motors — deterministically, every millisecond.

That is what hardware drivers exist for.



1) The Control Stack (One pipeline)

Every LinuxCNC machine, no matter how complex, always follows this pipeline:


G-code / GUI
      ↓
Trajectory Planner (math)
      ↓
Motion Controller (positions, velocities)
      ↓
HAL (signal bus)
      ↓
Hardware Driver
      ↓
Physical Pins
      ↓
Motor / Encoder / VFD / Switch




2) What a “Hardware Driver” Really Is



A real-time signal translator that turns numbers into electricity and electricity back into numbers.

It converts:

LinuxCNC produces	Hardware needs
Position numbers	Step pulses
Velocity numbers	PWM
Enable bits	        Logic voltages
Encoder counts	        Feedback numbers

The driver is where software touches physics.

Why HAL Exists

LinuxCNC never lets motion code talk to hardware directly.

Instead:

Motion → HAL → Driver → Hardware


HAL is a real-time signal bus, just like:

PCI bus

CAN bus

EtherCAT



Every driver connects to HAL using:


pins

signals

threads

This makes LinuxCNC modular, debuggable, and hardware-independent.

Two Kinds of Hardware Drivers

There are only two categories.


3) CPU-Driven Drivers (software timing)

Examples:

Parallel port

Raspberry Pi GPIO

mb2hal (Modbus)

Here:

Linux CPU
  └─ Generates step pulses
  └─ Samples encoders
  └─ Toggles pins


Pros:

Cheap

Simple

No special hardware


Cons:

Jitter

Limited speed

Not industrial-grade

Used for:

Hobby CNC

Simple automation


4) Hardware-Offloaded Drivers (FPGA / smart I/O)

Examples:

Mesa (HostMot2)

EtherCAT drives

Industrial servo controllers

Here:

LinuxCNC → sends numbers
Hardware → generates waveforms




The FPGA or drive:

Produces step pulses

Counts encoders

Runs PWM

Handles limits

LinuxCNC just streams:

Position

Velocity

Enable

This is how real CNC controllers work.



5) Mesa & HostMot2 — The Industrial Core

Mesa cards contain an FPGA running HostMot2 firmware.



Architecture:

LinuxCNC
   ↓
hostmot2 driver
   ↓
PCI / Ethernet
   ↓
FPGA
   ↓
Stepgen / Encoder / PWM logic
   ↓
Physical pins


LinuxCNC never touches pins.
The FPGA does the real-time work.



6) Canonical Device Interface — Why Everything Looks the Same

LinuxCNC forces all hardware to expose the same HAL pins:

Function	HAL Pin
Stepper	        stepgen.N
Encoder	        encoder.N
Digital input	motion.digital-in-N
Analog out	motion.analog-out-N

So motion control never knows:

If it’s Mesa

Or Pi GPIO

Or EtherCAT

This is LinuxCNC’s hardware API.



7) What Really Happens When You Move an Axis



Example: X axis move

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
Motor turns


Feedback:

Encoder → driver → encoder.0.position → motion.position-fb


That is a closed-loop control system.