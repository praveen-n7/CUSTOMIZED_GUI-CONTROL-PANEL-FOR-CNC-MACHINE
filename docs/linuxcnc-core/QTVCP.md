# QtVCP — Qt-Based Virtual Control Panels for LinuxCNC

This document describes the structure, role, and integration workflow of **QtVCP** within **:contentReference[oaicite:0]{index=0}**.

QtVCP provides a **Qt-based framework** for developing modern, highly customizable CNC graphical user interfaces and control panels using Python and HAL.

---

## 1. Overview

QtVCP is a GUI framework built on:
- Qt (via PyQt / PySide)
- Python
- LinuxCNC APIs (HAL, NML, status, command)

QtVCP enables the creation of:
- Full-featured CNC control interfaces
- Custom operator panels
- Touch-friendly and high-resolution UIs
- Machine-specific workflows

QtVCP is designed as a **successor-class framework** to GTK-based solutions, offering improved flexibility and modern UI capabilities.

---

## 2. Architectural Position in LinuxCNC

QtVCP operates as a user-space application layered above the LinuxCNC core.

High-level interaction model:

Operator
↓
QtVCP (Qt + Python)
↓
Python Handler Logic
↓
HAL / NML / Status APIs
↓
LinuxCNC Motion Controller
↓
Realtime HAL
↓
Machine Hardware


QtVCP does not execute realtime logic. All realtime operations remain within HAL and motion components.

---

## 3. Core Components of QtVCP

A typical QtVCP-based GUI consists of:

ui_file.ui → Qt Designer UI layout
handler.py → Python logic and callbacks
ini configuration→ GUI integration and startup
HAL connections → Realtime signal wiring


Each component has a clearly defined responsibility.

---

## 4. UI Layout Definition (Qt Designer)

QtVCP interfaces are designed using **Qt Designer**.

The `.ui` file defines:
- Widget hierarchy
- Layout management
- Signal-slot bindings
- Visual styling

Supported widgets include:
- Buttons, sliders, and indicators
- DROs and displays
- Tabbed and stacked layouts
- Touch-optimized controls

The `.ui` file contains **no execution logic**.

---

## 5. Python Handler Model

Behavior is implemented in Python handler files.

Responsibilities include:
- Responding to Qt signals
- Interacting with HAL pins
- Accessing LinuxCNC status and command channels
- Managing GUI state and interlocks

Handlers are automatically loaded by QtVCP at runtime and bound to the UI elements defined in the `.ui` file.

---

## 6. HAL Integration

QtVCP provides direct integration with HAL through Python bindings.

Capabilities include:
- Creating HAL pins from UI elements
- Reading realtime machine inputs
- Writing control outputs
- Binding indicators to HAL state

Typical mappings:
- Push button → HAL bit output
- Indicator LED → HAL bit input
- Slider → HAL float output

This enables deterministic interaction between the GUI and machine hardware.

---

## 7. NML and Status Interfaces

QtVCP interfaces with LinuxCNC using:
- NML for motion and mode commands
- Status channels for machine feedback

Common interactions:
- Mode switching (MANUAL / AUTO / MDI)
- Program execution control
- Tool and spindle operations
- Machine state monitoring

These interactions occur outside the realtime domain.

---

## 8. Integration via INI Configuration

QtVCP-based GUIs are integrated through the LinuxCNC INI file.

Typical configuration entry:

```ini
[DISPLAY]
DISPLAY = qtvcp
QTVCP = my_custom_panel.ui
Optional handler files and user options may also be specified depending on the GUI design.

9. Customization Scope
QtVCP supports:

Fully custom CNC control screens

Machine-specific operator workflows

Embedded auxiliary panels

Advanced visual styling and theming

Multi-screen and high-DPI layouts

Customization is performed without modifying LinuxCNC core components.

10. QtVCP Compared to Other LinuxCNC GUI Frameworks
Framework	Technology	Scope
AXIS	Tk	Reference GUI
Gmoccapy	GTK	Full operator GUI
GladeVCP	GTK	Auxiliary panels
QtVCP	Qt	Full custom GUIs and panels
QtVCP is intended for systems requiring maximum UI flexibility and modern interface design.