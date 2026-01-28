# Gmoccapy — LinuxCNC Advanced GTK GUI (Internal Architecture & Customization)

## 1. What Gmoccapy Really Is

Gmoccapy is **not** a theme, skin, or visual add-on.

It is a **full Python-based Human–Machine Interface (HMI)** for LinuxCNC that translates operator actions into:

- HAL pin interactions
- NML motion commands
- Machine state control
- IO and status updates

Gmoccapy sits **between the operator and the LinuxCNC core**.

### High-Level Architecture

Human
↓
Gmoccapy (GTK + Python)
↓
LinuxCNC APIs (HAL / NML)
↓
Motion Controller
↓
Realtime HAL
↓
Hardware (Mesa / GPIO / Drives)


---

## 2. Where Gmoccapy Lives

On a standard LinuxCNC installation:

/usr/share/linuxcnc/gmoccapy/


Key files:

gmoccapy.py → Main application entry point
gmoccapy.glade → GTK UI layout (widgets & panels)
handler.py → User interaction & custom logic
gmoccapy_handler.py → Core callbacks and signal glue


> Editing `.glade` only affects appearance.  
> **Behavior is controlled by Python handlers.**

---

## 3. Technology Stack

| Layer | Purpose |
|------|--------|
| GTK+ / Glade | UI layout and widgets |
| Python | Application logic and callbacks |
| LinuxCNC Python API | Motion, IO, and machine state |
| HAL | Realtime signal wiring |
| NML | Messaging with motion controller |

Gmoccapy is **event-driven control software**, not MVC or a web-style UI.

---

## 4. Startup Flow

Understanding this flow is essential for customization.

LinuxCNC starts
↓
DISPLAY = gmoccapy
↓
gmoccapy.py launches
↓
Loads gmoccapy.glade
↓
Binds GTK signals to Python handlers
↓
Initializes LinuxCNC command & status interfaces
↓
GUI enters GTK main event loop


Every button press, DRO update, or LED change is a **callback execution**.

---

## 5. Role of Glade (GTK UI)

Glade defines only:

- Buttons
- Labels
- Containers
- Tabs and panels

Glade **does not execute logic**.

Examples:
- Button → triggers a Python callback
- Label → updated by Python code
- LED → reflects HAL pin state

Editing only Glade means you are doing **UI layout**, not CNC control.

---

## 6. Handler Files (Control Logic)

### `handler.py`

This file contains **custom machine logic**.

Typical responsibilities:
- Button callbacks
- HAL pin reads and writes
- Machine state checks
- Safety logic
- Enabling/disabling UI controls

Conceptual logic example:

If machine is not homed:
Disable jog controls
Else:
Enable jog controls


This is **operator safety logic**, not cosmetic behavior.

---

## 7. HAL Integration

Gmoccapy communicates with HAL via Python HAL bindings.

Capabilities:
- Read realtime inputs (limits, estop, sensors)
- Write outputs (relays, LEDs, indicators)
- Bind UI elements to realtime machine state

Data flow model:

HAL pin → Python → GTK widget
GTK action → Python → HAL pin


This is how UI actions affect real hardware.

---

## 8. NML Messaging

Some machine commands cannot use HAL.

NML is used for:
- Mode switching (MANUAL / AUTO / MDI)
- Program start, pause, stop
- Tool changes
- Trajectory control

If HAL is **wiring**, NML is the **command bus**.

---

## 12. Core Mental Model

> Gmoccapy is a **Python control application**  
> using **GTK for layout**,  
> **HAL for realtime wiring**,  
> and **NML for motion control**.

Understanding this fully means you are working at the **correct abstractio