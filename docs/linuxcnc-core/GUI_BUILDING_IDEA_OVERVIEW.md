# Customized CNC GUI Panel Using Gmoccapy, Glade, and LinuxCNC

This document describes the workflow and structure for building a **customized CNC operator GUI panel** using **:contentReference[oaicite:0]{index=0}**, **:contentReference[oaicite:1]{index=1}**, GTK Glade, and Python.

The approach focuses on **machine-specific customization** while remaining compatible with standard LinuxCNC installations and upgrade paths.

---

## 1. System Overview

The customized GUI operates as a Python-based Human–Machine Interface layered on top of LinuxCNC. Operator interactions are translated into machine behavior using HAL signals and NML commands.

High-level data flow:

Operator
↓
Gmoccapy (GTK + Python)
↓
Python Handlers
↓
HAL / NML
↓
LinuxCNC Motion Controller
↓
Realtime Hardware


The system separates responsibilities clearly:
- GTK/Glade defines layout
- Python defines behavior
- HAL provides realtime signal wiring

---

## 2. Environment Requirements

- LinuxCNC installed and operational
- Existing machine configuration
- Access to GTK Glade
- Python support enabled in LinuxCNC

The customization process assumes a functioning base machine configuration.

---

## 3. Custom GUI Workspace Structure

Custom GUI assets are stored within the machine configuration directory to avoid modifying system-level files.

Example structure:

configs/my_cnc/
├── my_cnc.ini
├── my_cnc.hal
└── gui/
├── gmoccapy.glade
└── custom_handler.py


This structure ensures portability and upgrade safety.

---

## 4. INI File Integration

The LinuxCNC INI file references the customized GUI components:

```ini
[DISPLAY]
DISPLAY = gmoccapy
GLADE_FILE = gui/gmoccapy.glade
HANDLER_FILE = gui/custom_handler.py
At startup, LinuxCNC loads the specified Glade layout and Python handler instead of the default system files.

5. GUI Layout Definition (Glade)
The .glade file defines:

Widget hierarchy

Visual layout

GTK signal bindings

Typical widgets include:

Buttons

Labels

Indicators

Sliders

Containers

The Glade file does not contain executable logic. All widget behavior is delegated to Python handlers via GTK signals.

6. Python Handler Architecture
Custom logic is implemented in the handler file.

Responsibilities include:

GTK signal callbacks

HAL pin creation and access

Machine state interaction

UI state control

Minimal structural pattern:

class HandlerClass:
    def __init__(self, halcomp, builder, useropts):
        self.hal = halcomp
        self.builder = builder

def get_handlers(halcomp, builder, useropts):
    return [HandlerClass(halcomp, builder, useropts)]
GTK signal names defined in Glade must correspond exactly to method names in the handler class.

7. HAL Integration
The GUI interacts with the realtime system through HAL pins created in Python.

Typical use cases:

Button → HAL output pin

LED → HAL input pin

Slider → HAL float pin

Example HAL pin creation:

self.hal.newpin("coolant_enable", hal.HAL_BIT, hal.HAL_OUT)
These pins are connected to machine logic via the main HAL configuration.

8. HAL Signal Wiring
GUI HAL pins are linked to machine-level HAL components using standard net statements.

Example:

net coolant-enable gui.coolant_enable => coolant.mist
This enables direct interaction between GUI controls and machine hardware.

9. Optional Embedded Panels
Additional functionality can be added through embedded control panels, including:

Tool probing interfaces

MPG and jog controls

Diagnostic panels

Custom macro execution

These panels integrate using the same Glade, Python, and HAL principles.

10. Runtime Verification
Verification is typically performed in stages:

GUI load confirmation

GTK callback execution

HAL pin visibility

Machine response validation

Common diagnostic tools:

Terminal logs

halshow

LinuxCNC status outputs

11. Common Integration Issues
Issue	Cause
GUI fails to load	Incorrect INI paths
Widget inactive	Signal-handler mismatch
Python exceptions	Handler not registered
HAL pin missing	Pin not created in handler
No machine response	HAL net not connected
Resolution requires correcting configuration-level mismatches rather than modifying core code.

12. Summary
This approach enables development of machine-specific CNC operator interfaces while maintaining a clean separation between layout, logic, and realtime control.

The resulting system remains:

Maintainable

Upgrade-safe

Aligned with LinuxCNC architecture