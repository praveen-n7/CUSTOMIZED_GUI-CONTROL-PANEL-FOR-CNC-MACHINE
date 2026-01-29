# GladeVCP — Custom Virtual Control Panels for LinuxCNC

## 1. What GladeVCP Really Is

GladeVCP is **not a full LinuxCNC GUI**.

It is a framework for building **custom Virtual Control Panels (VCPs)** using:

- GTK widgets (designed in Glade)
- Python callbacks
- HAL pin connections

GladeVCP panels are meant to be **embedded into existing LinuxCNC GUIs** (AXIS, Gmoccapy, etc.) or run as standalone auxiliary panels.

---

## 2. Purpose of GladeVCP

GladeVCP exists to solve one problem:

> **How do I add machine-specific controls to a LinuxCNC GUI without rewriting the GUI itself?**

Typical use cases:
- Custom machine buttons
- Special macros
- Indicator LEDs
- Manual IO controls
- Operator-specific workflows

GladeVCP is **extension**, not replacement.

---

## 3. Where GladeVCP Fits in LinuxCNC

High-level position:

Human
↓
LinuxCNC Main GUI (AXIS / Gmoccapy)
↓
Embedded GladeVCP Panel
↓
Python Callbacks + HAL Pins
↓
Realtime HAL
↓
Hardware


GladeVCP **does not control motion directly**.  
It interacts through HAL and LinuxCNC APIs.

---

## 4. Core Components of GladeVCP

A GladeVCP panel consists of three parts:

panel.glade → GTK layout
panel.py → Python callback logic
panel.hal → HAL connections (optional)


Each part has a **strict responsibility**.

---

## 5. Role of Glade (`.glade` file)

The `.glade` file defines only:

- Buttons
- Labels
- LEDs
- Sliders
- Containers

Glade **contains no logic**.

Widgets are given names that Python and HAL can reference.

Example responsibilities:
- Button exists
- LED exists
- Layout exists

No behavior happens here.

---

## 6. Python Handler (Control Logic)

The Python file provides:

- Callback functions for GTK signals
- Access to HAL pins
- Access to LinuxCNC status and commands

Typical logic includes:
- Button press handling
- Updating labels or LEDs
- Reading machine state
- Writing HAL outputs

Conceptual example:

Button pressed
↓
Python callback
↓
Write HAL pin
↓
Hardware reacts


This is where **behavior lives**.

---

## 7. HAL Integration

GladeVCP is tightly integrated with HAL.

Capabilities:
- Create HAL pins from GTK widgets
- Read HAL inputs into the UI
- Write HAL outputs from UI actions

Common bindings:
- Button → HAL bit output
- LED → HAL bit input
- Slider → HAL float output

Data flow:

HAL pin ↔ Python ↔ GTK widget


This makes GladeVCP suitable for **realtime-safe interaction**.

---

## 8. How GladeVCP Is Loaded

GladeVCP panels can be loaded in multiple ways:

### Embedded into a GUI
- Embedded inside AXIS
- Embedded inside Gmoccapy tabs or panels

### Standalone panel
- Launched as a separate window
- Used as an auxiliary control interface

Loading is done via:
- INI file configuration
- Command-line invocation
- GUI-specific embedding mechanisms

---

## 9. What GladeVCP Is NOT

GladeVCP is **not**:
- A motion controller
- A trajectory planner
- A replacement for AXIS or Gmoccapy
- A realtime component

All realtime behavior must live in HAL or realtime components.

---

## 10. GladeVCP vs Gmoccapy

| Aspect | GladeVCP | Gmoccapy |
|------|---------|---------|
| Scope | Control panel | Full GUI |
| Motion control | No | Yes |
| UI complexity | Small / focused | Large / complete |
| Custom logic | Yes | Yes |
| Typical use | Add-on panel | Primary interface |

They solve **different problems** and are often used together.

---

## 11. Correct Mental Model

> GladeVCP is a **GTK-based control panel framework**  
> that connects **custom UI elements**  
> to **HAL pins and Python logic**  
> without touching the core LinuxCNC GUI.