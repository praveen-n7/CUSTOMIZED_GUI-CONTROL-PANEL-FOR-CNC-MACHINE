# ClassicLadder in LinuxCNC — The PLC Engine

ClassicLadder is the **PLC inside LinuxCNC**.  
It controls **machine logic**, not motion.

Motion decides **how motors move**.  
ClassicLadder decides **whether they are allowed to move**.

---

## 1. Where ClassicLadder Lives

GUI / G-code
↓
Motion Controller
↓
HAL (real-time signal bus)
↓
ClassicLadder (PLC)
↓
Hardware Drivers
↓
Sensors, Valves, Relays, I/O


ClassicLadder sits inside **HAL** and sees everything.

---

## 2. What It Controls

ClassicLadder does NOT move axes.

It controls:
- Spindle enable
- Coolant
- Tool changers
- Doors & interlocks
- Probes
- Pneumatics
- Alarms
- Safety logic

Motion plans trajectories.  
ClassicLadder runs the **machine**.

---

## 3. PLC Memory Model

ClassicLadder uses standard PLC memory:

| Type | Meaning |
|------|--------|
| `%I` | Inputs |
| `%Q` | Outputs |
| `%M` | Internal relays |
| `%T` | Timers |
| `%C` | Counters |
| `%W` | Words |
| `%F` | Floats |

Example:
%I0 → Limit switch
%Q3 → Solenoid valve
%T0.Q → Timer done
%C2.V → Counter value


---

## 4. How ClassicLadder Talks to HAL

LinuxCNC maps PLC memory to HAL pins:

classicladder.0.in-00 → %I0
classicladder.0.out-03 → %Q3


Signal flow:

Sensor → HAL → %I → PLC logic → %Q → HAL → Relay → Machine


ClassicLadder becomes a **HAL-connected PLC**.

---

## 5. Typical Workflow (Tool Change Example)

M6 command
↓
Motion stops
↓
ClassicLadder runs tool-changer ladder
↓
Sensors confirm tool in place
↓
PLC releases motion


Motion moves the machine.  
PLC decides when it is safe.

---

## 6. Why ClassicLadder Is Mandatory

Without a PLC:
- No safe tool change
- No door interlocks
- No probing
- No automation
- No alarms

With ClassicLadder:
LinuxCNC becomes a **real machine controller**.

---

## 7. One-Line Truth

> ClassicLadder is the PLC that controls **what a LinuxCNC machine is allowed to do**, while motion control decides **how it moves**.