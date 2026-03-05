#!/usr/bin/env python3
"""
QtVCP Panel Handler - Mode-Based Visibility Control
Version: 6.2 - ADDED MAX AXIS VELOCITY DISPLAY IN DRO
"""

from PyQt5.QtCore import Qt, QTimer, QObject, QEvent, QRect
from PyQt5.QtWidgets import QButtonGroup, QFileDialog, QShortcut, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton, QMenu, QTableWidgetItem, QMessageBox, QAbstractItemView, QApplication, QSizePolicy
from PyQt5.QtGui import QTextCursor, QTextCharFormat, QColor, QKeySequence

# Enable HiDPI scaling — must be set BEFORE QApplication is created.
# QtVCP creates the QApplication, so we set these attributes here as early as possible.
try:
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
except Exception:
    pass
from qtvcp.core import Status, Action, Info
import linuxcnc
import os
import time
import math

STATUS = Status()
ACTION = Action()
INFO = Info()

# — ADDED: KEY RELEASE STOP MIRROR —
class KeyReleaseFilter(QObject):
    """Minimal event filter to handle arrow key release for jog stop"""
    def __init__(self, handler):
        super().__init__()
        self.handler = handler
    
    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyRelease and not event.isAutoRepeat():
            key = event.key()
            if key == Qt.Key_Right:
                self.handler.w.btn_jog_xplus.released.emit()
                return True
            elif key == Qt.Key_Left:
                self.handler.w.btn_jog_xminus.released.emit()
                return True
            elif key == Qt.Key_Up:
                self.handler.w.btn_jog_yplus.released.emit()
                return True
            elif key == Qt.Key_Down:
                self.handler.w.btn_jog_yminus.released.emit()
                return True
        return False
# — END ADDED: KEY RELEASE STOP MIRROR —

# — ADDED: JOINT ASSIGNMENT DIALOG —
class JointAssignmentDialog(QDialog):
    """Modal dialog for assigning joints to home buttons"""
    def __init__(self, parent, current_mappings, joint_count):
        super().__init__(parent)
        self.setWindowTitle("Joint Assignment")
        self.setModal(True)
        self.setMinimumWidth(350)
        
        # Store parameters
        self.current_mappings = current_mappings.copy()
        self.joint_count = joint_count
        self.result_mappings = None
        
        # Create combo boxes
        self.combo_x = QComboBox()
        self.combo_y = QComboBox()
        self.combo_z = QComboBox()
        
        # Populate combos with joint options
        for i in range(joint_count):
            self.combo_x.addItem(f"Joint {i}", i)
            self.combo_y.addItem(f"Joint {i}", i)
            self.combo_z.addItem(f"Joint {i}", i)
        
        # Set current selections
        self.combo_x.setCurrentIndex(current_mappings['x'])
        self.combo_y.setCurrentIndex(current_mappings['y'])
        self.combo_z.setCurrentIndex(current_mappings['z'])
        
        # Layout
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title label
        title_label = QLabel("Assign Joints to Home Buttons")
        title_label.setStyleSheet("font-size: 12pt; font-weight: bold; color: #2c3e50;")
        layout.addWidget(title_label)
        
        # HOME X row
        x_layout = QHBoxLayout()
        x_label = QLabel("HOME X:")
        x_label.setMinimumWidth(80)
        x_label.setStyleSheet("font-weight: bold; font-size: 10pt;")
        x_layout.addWidget(x_label)
        self.combo_x.setStyleSheet(self.get_combo_style())
        x_layout.addWidget(self.combo_x)
        layout.addLayout(x_layout)
        
        # HOME Y row
        y_layout = QHBoxLayout()
        y_label = QLabel("HOME Y:")
        y_label.setMinimumWidth(80)
        y_label.setStyleSheet("font-weight: bold; font-size: 10pt;")
        y_layout.addWidget(y_label)
        self.combo_y.setStyleSheet(self.get_combo_style())
        y_layout.addWidget(self.combo_y)
        layout.addLayout(y_layout)
        
        # HOME Z row
        z_layout = QHBoxLayout()
        z_label = QLabel("HOME Z:")
        z_label.setMinimumWidth(80)
        z_label.setStyleSheet("font-weight: bold; font-size: 10pt;")
        z_layout.addWidget(z_label)
        self.combo_z.setStyleSheet(self.get_combo_style())
        z_layout.addWidget(self.combo_z)
        layout.addLayout(z_layout)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        self.btn_confirm = QPushButton("CONFIRM")
        self.btn_confirm.setMinimumHeight(40)
        self.btn_confirm.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: 2px solid #1e8449;
                font-weight: bold;
                border-radius: 4px;
                font-size: 11pt;
            }
            QPushButton:hover {
                border-color: #ffffff;
            }
            QPushButton:pressed {
                background-color: #1e8449;
            }
        """)
        self.btn_confirm.clicked.connect(self.accept_changes)
        
        self.btn_cancel = QPushButton("CANCEL")
        self.btn_cancel.setMinimumHeight(40)
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #c0392b;
                color: white;
                border: 2px solid #943126;
                font-weight: bold;
                border-radius: 4px;
                font-size: 11pt;
            }
            QPushButton:hover {
                border-color: #ffffff;
            }
            QPushButton:pressed {
                background-color: #943126;
            }
        """)
        self.btn_cancel.clicked.connect(self.reject)
        
        button_layout.addWidget(self.btn_confirm)
        button_layout.addWidget(self.btn_cancel)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
        # Apply dialog styling
        self.setStyleSheet("""
            QDialog {
                background-color: #ecf0f1;
            }
        """)
    
    def get_combo_style(self):
        """Return consistent combo box styling"""
        return """
            QComboBox {
                background-color: white;
                border: 2px solid #bdc3c7;
                border-radius: 4px;
                padding: 5px;
                font-size: 10pt;
                min-height: 30px;
            }
            QComboBox:hover {
                border-color: #3498db;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #2c3e50;
                margin-right: 5px;
            }
        """
    
    def accept_changes(self):
        """User confirmed - validate and store new mappings"""
        # — ADDED: UNIQUE JOINT VALIDATION —
        # Get selected joints
        selected_x = self.combo_x.currentData()
        selected_y = self.combo_y.currentData()
        selected_z = self.combo_z.currentData()
        
        # Check for duplicate joint assignments
        selected_joints = [selected_x, selected_y, selected_z]
        if len(selected_joints) != len(set(selected_joints)):
            # Duplicates detected - show error
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.critical(
                self,
                "Invalid Joint Assignment",
                "Each Home button must be assigned to a unique joint.",
                QMessageBox.Ok
            )
            return  # Do not close dialog or update mappings
        # — END ADDED: UNIQUE JOINT VALIDATION —
        
        # All selections are unique - proceed
        self.result_mappings = {
            'x': selected_x,
            'y': selected_y,
            'z': selected_z
        }
        self.accept()
    
    def get_mappings(self):
        """Return the selected mappings (None if cancelled)"""
        return self.result_mappings
# — END ADDED: JOINT ASSIGNMENT DIALOG —

# ─────────────────────────────────────────────────────────────────────────────
# RESPONSIVE LAYOUT: Overlay resize filter
# Keeps frame_tool_panel (floating overlay) positioned over gcode_viewer area
# whenever the main window is resized or shown.
# ─────────────────────────────────────────────────────────────────────────────
class _OverlayResizeFilter(QObject):
    """Event filter that repositions the tool-panel overlay on window resize."""
    def __init__(self, handler):
        super().__init__()
        self.handler = handler

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Resize, QEvent.Show):
            try:
                self.handler._reposition_tool_panel()
            except Exception:
                pass
        return False


class HandlerClass:
    def __init__(self, halcomp, widgets, paths):
        self.hal = halcomp
        self.w = widgets
        self.command = linuxcnc.command()
        self.stat = linuxcnc.stat()
        
        # Jog settings
        self.jog_speed = 500  # mm/min
        self.jog_increment = 10.0
        self.jog_mode = "increment"
        
        # Spindle settings
        self.spindle_speed = 1000
        
        # Current mode
        self.current_mode = "MANUAL"
        
        # Auto mode settings
        self.loaded_program_path = None
        self.loaded_program_lines = []
        self.auto_feedrate_override = 100
        self.last_highlighted_line = -1
        
        # — ADDED: DYNAMIC HOME BUTTON BINDING —
        # Default joint to axis mapping
        self.home_x_joint = 0
        self.home_y_joint = 1
        self.home_z_joint = 2
        # — END ADDED: DYNAMIC HOME BUTTON BINDING —
        
        # — ADDED: MAX AXIS VELOCITY TRACKING —
        self.max_velocity = 0.0
        self.is_metric = True  # Default to metric
        # — END ADDED: MAX AXIS VELOCITY TRACKING —
        
        # — ADDED: TOOL MANAGEMENT STATE —
        self.tool_panel_visible = False
        self.tool_file_path = None        # Resolved at init from INI
        self.tool_table_modified = False  # Track unsaved edits
        # — END ADDED: TOOL MANAGEMENT STATE —

        # — ADDED: TOOL INFO PANEL CHANGE TRACKING —
        # Track last known values to avoid redundant file reads and UI flicker
        self._last_tool_in_spindle = -1          # -1 forces first update
        self._last_spindle_speed   = -1.0        # -1.0 forces first Vc update
        self._last_task_mode       = -1          # track mode for AUTO indicator
        self._tool_info_cache      = {}          # cached data for current tool
        # — END ADDED: TOOL INFO PANEL CHANGE TRACKING —

        # — ADDED: COOLANT STATUS SYNC —
        # None forces the very first periodic_update() to always paint the UI
        self._last_coolant_state = None
        # — END ADDED: COOLANT STATUS SYNC —

        # — ADDED: TOUCH-OFF AND VIEW TAB STATE —
        self._touchoff_axis = None   # last selected axis for SET SELECTED
        # — END ADDED: TOUCH-OFF AND VIEW TAB STATE —
        
    def initialized__(self):
        """Called after widgets are initialized"""
        print("="*50)
        print("QtVCP Panel - Mode-Based Visibility Control")
        print("Version 6.2 - MAX AXIS VELOCITY DISPLAY")
        print("="*50)

        # ── RESPONSIVE LAYOUT: Maximise window on startup ─────────────────
        try:
            self.w.showMaximized()
        except Exception as e:
            print(f"showMaximized note: {e}")

        # ── RESPONSIVE LAYOUT: Overlay resize filter for tool panel ───────
        # frame_tool_panel floats as an absolute overlay over the gcode_viewer
        # area.  We keep it in sync whenever the window is resized.
        try:
            self._overlay_filter = _OverlayResizeFilter(self)
            self.w.installEventFilter(self._overlay_filter)
        except Exception as e:
            print(f"Overlay resize filter note: {e}")

        # Configure DRO
        self.setup_dro()
        
        # — ADDED: GCODE GRAPHICS INITIALIZATION —
        # GCodeGraphics widget needs explicit initialization in some QtVCP versions.
        # Force show + reset view so the OpenGL canvas is visible on startup.
        try:
            if hasattr(self.w, 'gcode_viewer'):
                self.w.gcode_viewer.show()
                self.w.gcode_viewer.setVisible(True)
                # Force the GL canvas to initialise and paint itself
                try:
                    self.w.gcode_viewer.set_current_view()
                except Exception:
                    pass
                try:
                    self.w.gcode_viewer.updateGL()
                except Exception:
                    pass
                # Raise it so it is not hidden behind other widgets at startup
                self.w.gcode_viewer.lower()   # send to back so DRO overlays on top
                print("✓ GCode Graphics viewer initialised and visible")
            else:
                print("⚠ gcode_viewer widget not found - check widget name in UI file")
        except Exception as e:
            print(f"GCode Graphics init error: {e}")
        # — END ADDED: GCODE GRAPHICS INITIALIZATION —
        
        # — ADDED: DRO VISIBILITY FIX —
        # Ensure DRO GroupBox appears on top of GCodeGraphics viewer
        try:
            if hasattr(self.w, 'groupBox_dro'):
                self.w.groupBox_dro.raise_()
                print("✓ DRO display raised to top layer")
        except Exception as e:
            print(f"DRO raise note: {e}")
        # — END ADDED: DRO VISIBILITY FIX —
        
        # — ADDED: DETECT MACHINE UNITS —
        # Check if machine is configured for metric or imperial
        try:
            linear_units = INFO.LINEAR_UNITS
            if linear_units and 'mm' in linear_units.lower():
                self.is_metric = True
            elif linear_units and ('inch' in linear_units.lower() or 'in' in linear_units.lower()):
                self.is_metric = False
            else:
                # Fallback: check from INI file
                self.is_metric = True  # Default
        except:
            self.is_metric = True  # Default to metric
        # — END ADDED: DETECT MACHINE UNITS —
        
        # Setup mode button group
        self.mode_group = QButtonGroup()
        self.mode_group.addButton(self.w.btn_mode_manual)
        self.mode_group.addButton(self.w.btn_mode_mdi)
        self.mode_group.addButton(self.w.btn_mode_auto)
        self.mode_group.setExclusive(True)
        
        # Setup jog increment button group
        self.jog_increment_group = QButtonGroup()
        self.jog_increment_group.addButton(self.w.btn_jog_continuous)
        self.jog_increment_group.addButton(self.w.btn_jog_10mm)
        self.jog_increment_group.addButton(self.w.btn_jog_1mm)
        self.jog_increment_group.addButton(self.w.btn_jog_0_1mm)
        self.jog_increment_group.addButton(self.w.btn_jog_0_01mm)
        self.jog_increment_group.setExclusive(True)
        
        # Connect mode buttons
        self.w.btn_mode_manual.clicked.connect(self.switch_to_manual)
        self.w.btn_mode_mdi.clicked.connect(self.switch_to_mdi)
        self.w.btn_mode_auto.clicked.connect(self.switch_to_auto)
        
        # Connect machine control buttons
        self.w.btn_estop.clicked.connect(self.toggle_estop)
        self.w.btn_power.clicked.connect(self.toggle_power)
        
        # — MODIFIED: HOME BUTTON WITH DROPDOWN MENU —
        # Create dropdown menu for HOME button
        self.home_menu = QMenu(self.w)
        self.home_menu.setStyleSheet("""
            QMenu {
                background-color: #2c3e50;
                color: white;
                border: 2px solid #1c5980;
                font-weight: bold;
                font-size: 11pt;
            }
            QMenu::item {
                padding: 8px 30px;
                background-color: transparent;
            }
            QMenu::item:selected {
                background-color: #3498db;
            }
        """)
        
        # Add menu actions
        action_home_all = self.home_menu.addAction("Home All")
        action_home_x = self.home_menu.addAction("Home X")
        action_home_y = self.home_menu.addAction("Home Y")
        action_home_z = self.home_menu.addAction("Home Z")
        
        # Connect menu actions to functions
        action_home_all.triggered.connect(self.home_all)
        action_home_x.triggered.connect(self.home_x_axis)
        action_home_y.triggered.connect(self.home_y_axis)
        action_home_z.triggered.connect(self.home_z_axis)
        
        # Set menu to HOME button
        self.w.btn_home.setMenu(self.home_menu)
        # — END MODIFIED: HOME BUTTON WITH DROPDOWN MENU —
        
        # — ADDED: JOINT SELECT BUTTON —
        # Connect joint assignment dialog button
        self.w.btn_joint_select.clicked.connect(self.open_joint_assignment_dialog)
        # — END ADDED: JOINT SELECT BUTTON —
        
        # Connect MDI controls
        self.w.btn_mdi_execute.clicked.connect(self.execute_mdi)
        self.w.btn_mdi_clear.clicked.connect(self.clear_mdi)
        self.w.text_mdi_input.returnPressed.connect(self.execute_mdi)
        
        # Connect Auto controls
        self.w.btn_load_program.clicked.connect(self.load_program)
        self.w.btn_cycle_start.clicked.connect(self.cycle_start)
        self.w.btn_pause.clicked.connect(self.pause_program)
        self.w.btn_stop.clicked.connect(self.stop_program)
        
        # Connect jog increment buttons
        self.w.btn_jog_continuous.clicked.connect(lambda: self.set_jog_increment("continuous"))
        self.w.btn_jog_10mm.clicked.connect(lambda: self.set_jog_increment(10.0))
        self.w.btn_jog_1mm.clicked.connect(lambda: self.set_jog_increment(1.0))
        self.w.btn_jog_0_1mm.clicked.connect(lambda: self.set_jog_increment(0.1))
        self.w.btn_jog_0_01mm.clicked.connect(lambda: self.set_jog_increment(0.01))
        
        # Connect jog velocity slider
        self.w.slider_jog_velocity.valueChanged.connect(self.update_jog_velocity)
        
        # Connect jog buttons
        self.w.btn_jog_xplus.pressed.connect(lambda: self.jog_joint(0, 1))
        self.w.btn_jog_xplus.released.connect(lambda: self.jog_stop(0))
        self.w.btn_jog_xminus.pressed.connect(lambda: self.jog_joint(0, -1))
        self.w.btn_jog_xminus.released.connect(lambda: self.jog_stop(0))
        
        self.w.btn_jog_yplus.pressed.connect(lambda: self.jog_joint(1, 1))
        self.w.btn_jog_yplus.released.connect(lambda: self.jog_stop(1))
        self.w.btn_jog_yminus.pressed.connect(lambda: self.jog_joint(1, -1))
        self.w.btn_jog_yminus.released.connect(lambda: self.jog_stop(1))
        
        self.w.btn_jog_zplus.pressed.connect(lambda: self.jog_joint(2, 1))
        self.w.btn_jog_zplus.released.connect(lambda: self.jog_stop(2))
        self.w.btn_jog_zminus.pressed.connect(lambda: self.jog_joint(2, -1))
        self.w.btn_jog_zminus.released.connect(lambda: self.jog_stop(2))
        
        # Connect spindle controls
        self.w.slider_spindle_speed.valueChanged.connect(self.update_spindle_speed_display)
        self.w.btn_spindle_fwd.clicked.connect(self.spindle_forward)
        self.w.btn_spindle_stop.clicked.connect(self.spindle_stop)
        self.w.btn_spindle_rev.clicked.connect(self.spindle_reverse)
        
        # Connect override sliders
        self.w.slider_feedrate.valueChanged.connect(self.update_feedrate_override)
        self.w.slider_rapidrate.valueChanged.connect(self.update_rapid_override)
        
        # Initialize displays
        self.update_spindle_speed_display(self.w.slider_spindle_speed.value())
        self.update_jog_velocity(self.w.slider_jog_velocity.value())
        
        # Start in MANUAL mode - show manual controls, hide MDI and Auto
        self.w.stackedWidget_modes.setCurrentIndex(0)  # Show page_manual
        self.w.btn_mode_manual.setChecked(True)

        # ── COOLING PANEL: Connect button defined in .ui ──────────────────────
        # groupBox_spindle and groupBox_cooling are now permanently placed in
        # layout_spindle_cooling_permanent inside layout_content in the .ui file.
        # They are always visible in MANUAL, MDI, and AUTO modes.
        try:
            self.w.btn_coolant_toggle.clicked.connect(self.coolant_toggle)
            print("✓ Cooling panel toggle button connected (always visible in all modes)")
        except Exception as e:
            print(f"Cooling panel connect note: {e}")
        # ── END COOLING PANEL SETUP ───────────────────────────────────────────
        
        # Setup periodic status update timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.periodic_update)
        self.timer.start(100)  # 100ms update rate
        
        # — ADDED: TOOL MANAGEMENT SETUP —
        self.setup_tool_management()
        # — END ADDED: TOOL MANAGEMENT SETUP —

        # — ADDED: TOUCH-OFF SECTION SETUP —
        self.setup_touchoff_section()
        # — END ADDED: TOUCH-OFF SECTION SETUP —

        # — ADDED: PREVIEW / OFFSET PAGE TABS SETUP —
        self.setup_graphics_tabs()
        # — END ADDED: PREVIEW / OFFSET PAGE TABS SETUP —

        # — ADDED: AUTO MODE TOOL CHANGE REFRESH —
        # STATUS.tool-in-spindle-changed fires in ALL modes (MANUAL, MDI, AUTO).
        # This ensures table_tools refreshes when M6 executes during a program run.
        STATUS.connect('tool-in-spindle-changed', self._on_tool_in_spindle_changed)
        # — END ADDED: AUTO MODE TOOL CHANGE REFRESH —

        # — ADDED: TOOL INFO PANEL DYNAMIC PROPERTIES —
        # Set toolInfoRole dynamic properties so CSS selectors activate correctly
        try:
            _col_headers = [
                'lbl_col_toolno', 'lbl_col_diam', 'lbl_col_zoff',
                'lbl_col_vc', 'lbl_col_desc',
            ]
            _col_values = [
                'toolNoValue', 'toolDiameterValue', 'toolOffsetZValue',
                'toolVcValue', 'toolDescValue',
            ]
            for name in _col_headers:
                w = getattr(self.w, name, None)
                if w:
                    w.setProperty('toolInfoRole', 'colHeader')
                    w.style().unpolish(w)
                    w.style().polish(w)
            for name in _col_values:
                w = getattr(self.w, name, None)
                if w:
                    w.setProperty('toolInfoRole', 'colValue')
                    w.style().unpolish(w)
                    w.style().polish(w)
        except Exception as e:
            print(f"Tool info property note: {e}")
        # — END ADDED: TOOL INFO PANEL DYNAMIC PROPERTIES —
        
        # — ADDED: ARROW KEY TO JOG BUTTON MIRROR —
        # Create keyboard shortcuts that trigger existing jog button signals
        # Right Arrow → X+ button
        self.shortcut_x_plus = QShortcut(QKeySequence(Qt.Key_Right), self.w)
        self.shortcut_x_plus.activated.connect(lambda: self.w.btn_jog_xplus.pressed.emit())
        self.shortcut_x_plus.setAutoRepeat(False)
        
        # Left Arrow → X- button
        self.shortcut_x_minus = QShortcut(QKeySequence(Qt.Key_Left), self.w)
        self.shortcut_x_minus.activated.connect(lambda: self.w.btn_jog_xminus.pressed.emit())
        self.shortcut_x_minus.setAutoRepeat(False)
        
        # Up Arrow → Y+ button
        self.shortcut_y_plus = QShortcut(QKeySequence(Qt.Key_Up), self.w)
        self.shortcut_y_plus.activated.connect(lambda: self.w.btn_jog_yplus.pressed.emit())
        self.shortcut_y_plus.setAutoRepeat(False)
        
        # Down Arrow → Y- button
        self.shortcut_y_minus = QShortcut(QKeySequence(Qt.Key_Down), self.w)
        self.shortcut_y_minus.activated.connect(lambda: self.w.btn_jog_yminus.pressed.emit())
        self.shortcut_y_minus.setAutoRepeat(False)
        
        # Install key release filter for jog stop
        self.key_release_filter = KeyReleaseFilter(self)
        self.w.installEventFilter(self.key_release_filter)
        # — END ADDED: ARROW KEY TO JOG BUTTON MIRROR —
        
        print("\n*** STARTUP SEQUENCE ***")
        print("1. Click E-STOP to clear")
        print("2. Click POWER ON")
        print("3. Click HOME ALL (or HOME X, HOME Y, HOME Z individually)")
        print("4. Select mode:")
        print("   - MANUAL MODE: Jog controls + Spindle + Overrides visible")
        print("   - MDI MODE: MDI command input visible")
        print("   - AUTO MODE: Program loader + execution controls visible")
        print("\n*** MODE-BASED VISIBILITY ***")
        print("✓ Manual: Jog buttons + Spindle/Override (right panel)")
        print("✓ MDI: MDI controls only (right panel)")
        print("✓ Auto: Program loader + controls (right panel)")
        print("✓ Constant: DRO (overlaid on graphics), Mode buttons, E-STOP, POWER, HOME (always visible)")
        print("\n*** KEYBOARD JOG SHORTCUTS ***")
        print("✓ Arrow Keys in MANUAL mode:")
        print("  → (Right) = X+  |  ← (Left) = X-")
        print("  ↑ (Up) = Y+     |  ↓ (Down) = Y-")
        print("="*50 + "\n")
    
    def setup_dro(self):
        """Configure DRO displays with axis labels"""
        try:
            # X axis
            self.w.dro_x.setProperty('joint_number', 0)
            self.w.dro_x.setProperty('Qjoint_number', 0)
            self.w.dro_x.setProperty('reference_type', 0)
            self.w.dro_x.setProperty('metric_units', True)
            self.w.dro_x.setProperty('mm_text_template', 'X: %10.3f')
            
            # Y axis
            self.w.dro_y.setProperty('joint_number', 1)
            self.w.dro_y.setProperty('Qjoint_number', 1)
            self.w.dro_y.setProperty('reference_type', 0)
            self.w.dro_y.setProperty('metric_units', True)
            self.w.dro_y.setProperty('mm_text_template', 'Y: %10.3f')
            
            # Z axis
            self.w.dro_z.setProperty('joint_number', 2)
            self.w.dro_z.setProperty('Qjoint_number', 2)
            self.w.dro_z.setProperty('reference_type', 0)
            self.w.dro_z.setProperty('metric_units', True)
            self.w.dro_z.setProperty('mm_text_template', 'Z: %10.3f')
            
            print("✓ DRO configured (X, Y, Z) - compact overlay at top-left with axis labels")
        except Exception as e:
            print(f"DRO note: {e}")
    
    def switch_to_manual(self):
        """Switch to MANUAL mode - Show jog controls + spindle/overrides in right panel"""
        # Safety check - prevent mode switch during program execution
        if self.is_auto_running():
            print("ERROR: Cannot change mode - program is running!")
            self.w.btn_mode_auto.setChecked(True)
            return
        
        self.current_mode = "MANUAL"
        print("\n*** MANUAL MODE ACTIVATED ***")
        print("VISIBLE: Jog buttons, Spindle controls, Jog velocity, Overrides")
        print("HIDDEN: MDI controls, Auto controls")
        
        # Switch stacked widget to Manual page (index 0)
        # This automatically shows all manual controls including jog buttons
        self.w.stackedWidget_modes.setCurrentIndex(0)
        
        # Set LinuxCNC to manual mode
        try:
            self.command.mode(linuxcnc.MODE_MANUAL)
            self.command.wait_complete()
        except Exception as e:
            print(f"Mode switch error: {e}")
    
    def switch_to_mdi(self):
        """Switch to MDI mode - Show MDI controls only in right panel"""
        # Safety check - prevent mode switch during program execution
        if self.is_auto_running():
            print("ERROR: Cannot change mode - program is running!")
            self.w.btn_mode_auto.setChecked(True)
            return
        
        if not STATUS.machine_is_on():
            print("ERROR: Cannot switch to MDI - Power is OFF!")
            print("Click POWER ON first")
            self.w.btn_mode_manual.setChecked(True)
            return
        
        self.current_mode = "MDI"
        print("\n*** MDI MODE ACTIVATED ***")
        print("VISIBLE: MDI command input, Execute/Clear buttons, Command history")
        print("HIDDEN: Jog controls, Spindle controls, Auto controls")
        
        # Switch stacked widget to MDI page (index 1)
        self.w.stackedWidget_modes.setCurrentIndex(1)
        
        # Set LinuxCNC to MDI mode
        try:
            self.command.mode(linuxcnc.MODE_MDI)
            self.command.wait_complete()
        except Exception as e:
            print(f"Mode switch error: {e}")
        
        # Focus on MDI input field
        self.w.text_mdi_input.setFocus()
    
    def switch_to_auto(self):
        """Switch to AUTO mode - Show program loader + execution controls in right panel"""
        # Safety check - prevent mode switch during program execution
        if self.is_auto_running():
            print("ERROR: Cannot change mode - program is already running!")
            self.w.btn_mode_auto.setChecked(True)
            return
        
        if not STATUS.machine_is_on():
            print("ERROR: Cannot switch to AUTO - Power is OFF!")
            print("Click POWER ON first")
            self.w.btn_mode_manual.setChecked(True)
            return
        
        self.current_mode = "AUTO"
        print("\n*** AUTO MODE ACTIVATED ***")
        print("VISIBLE: Load Program, Program Preview, Cycle Start/Pause/Stop")
        print("HIDDEN: Jog controls, Spindle controls, MDI controls")
        
        # Switch stacked widget to Auto page (index 2)
        self.w.stackedWidget_modes.setCurrentIndex(2)
        
        # Set LinuxCNC to auto mode
        try:
            self.command.mode(linuxcnc.MODE_AUTO)
            self.command.wait_complete()
        except Exception as e:
            print(f"Mode switch error: {e}")
    
    def periodic_update(self):
        """Periodic status update"""
        try:
            self.stat.poll()
            
            # — ADDED: MAX AXIS VELOCITY CALCULATION —
            # Get current velocities for all joints
            max_vel = 0.0
            try:
                # Try to get actual_position velocity (derivative)
                # LinuxCNC stores velocity in machine units per second
                num_joints = INFO.JOINT_COUNT
                
                # Check if current_vel is available (total current velocity)
                if hasattr(self.stat, 'current_vel'):
                    # current_vel is in machine units per second
                    max_vel = abs(self.stat.current_vel)
                else:
                    # Fallback: Calculate from joint velocities
                    if hasattr(self.stat, 'joint_actual_position'):
                        # We can't directly get velocity from joint_actual_position
                        # So we'll use a different approach if available
                        pass
                
                # Convert to mm/min or inch/min for display
                # current_vel is in units/sec, convert to units/min
                max_vel_per_min = max_vel * 60.0
                
                # Update display
                if self.is_metric:
                    self.w.dro_velocity.setText(f"{max_vel_per_min:7.3f} mm/min")
                else:
                    self.w.dro_velocity.setText(f"{max_vel_per_min:7.3f} in/min")
                
            except Exception as e:
                # If velocity calculation fails, show 0
                if self.is_metric:
                    self.w.dro_velocity.setText("  0.000 mm/min")
                else:
                    self.w.dro_velocity.setText("  0.000 in/min")
            # — END ADDED: MAX AXIS VELOCITY CALCULATION —
            
        except:
            pass
        # — ADDED: keep tool status bar in sync with controller ——————————
        try:
            if self.tool_panel_visible:
                self._update_tool_status_bar()
        except Exception:
            pass
        # — END ADDED ——————————————————————————————————————————————————————
        # — ADDED: COOLANT STATUS SYNC ————————————————————————————————————
        # stat.poll() was already called above; read coolant fields directly.
        try:
            self._update_coolant_status()
        except Exception:
            pass
        # — END ADDED: COOLANT STATUS SYNC ———————————————————————————————
        # — ADDED: TOOL INFO PANEL UPDATE —
        try:
            self._update_tool_info_panel()
        except Exception:
            pass
        # — END ADDED: TOOL INFO PANEL UPDATE —
    
    def is_auto_running(self):
        """Check if auto mode program is running"""
        try:
            self.stat.poll()
            return (self.stat.task_mode == linuxcnc.MODE_AUTO and 
                    self.stat.interp_state != linuxcnc.INTERP_IDLE)
        except:
            return False
    
    def load_program(self):
        """Load G-code program"""
        if not STATUS.machine_is_on():
            print("ERROR: Power OFF!")
            return
        
        # Check if homed
        self.stat.poll()
        all_homed = all(self.stat.homed[i] == 1 for i in range(INFO.JOINT_COUNT))
        if not all_homed:
            print("\n" + "="*50)
            print("⚠ WARNING: NOT ALL AXES HOMED!")
            print("Running programs without homing may cause issues")
            print("Recommendation: Click HOME ALL first")
            print("="*50 + "\n")
        
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(
            None,
            "Select G-code Program",
            os.path.expanduser("~"),
            "G-code Files (*.ngc *.nc *.gcode);;All Files (*)",
            options=options
        )
        
        if file_path:
            try:
                # Load the program
                self.command.mode(linuxcnc.MODE_AUTO)
                self.command.wait_complete()
                ACTION.OPEN_PROGRAM(file_path)
                
                # Read and display preview
                with open(file_path, 'r') as f:
                    lines = f.readlines()
                    self.loaded_program_lines = lines
                    preview_text = ''.join(lines[:50])  # Show first 50 lines
                    if len(lines) > 50:
                        preview_text += f"\n... ({len(lines)} total lines)"
                    self.w.text_program_preview.setPlainText(preview_text)
                
                self.loaded_program_path = file_path
                self.w.label_11.setText(f"Loaded: {os.path.basename(file_path)}")
                print(f"\n✓ Program loaded: {file_path}")
                print(f"  Total lines: {len(lines)}")
                print(f"  Ready to run - Click CYCLE START")
                print("="*50 + "\n")

                # — ADDED: FORCE GCODE GRAPHICS REFRESH AFTER LOAD —
                # After ACTION.OPEN_PROGRAM the GL canvas needs a view reset
                # and repaint to actually draw the new toolpath.
                try:
                    if hasattr(self.w, 'gcode_viewer'):
                        # Small delay via QTimer to let LinuxCNC finish loading
                        from PyQt5.QtCore import QTimer as _QT
                        def _refresh_view():
                            try:
                                self.w.gcode_viewer.set_current_view()
                            except Exception:
                                pass
                            try:
                                self.w.gcode_viewer.updateGL()
                            except Exception:
                                pass
                        _QT.singleShot(300, _refresh_view)
                except Exception as _e:
                    print(f"GCode viewer refresh note: {_e}")
                # — END ADDED: FORCE GCODE GRAPHICS REFRESH —
                
            except Exception as e:
                print(f"ERROR loading program: {e}")
    
    def cycle_start(self):
        """Start program execution"""
        if not self.loaded_program_path:
            print("ERROR: No program loaded!")
            return
        
        if not STATUS.machine_is_on():
            print("ERROR: Power OFF!")
            return
        
        # Check if homed
        self.stat.poll()
        all_homed = all(self.stat.homed[i] == 1 for i in range(INFO.JOINT_COUNT))
        if not all_homed:
            print("\n" + "="*50)
            print("⚠ WARNING: NOT ALL AXES HOMED!")
            print("Program execution may fail")
            print("Recommendation: Click HOME ALL first")
            print("="*50 + "\n")
        
        try:
            print("\n*** CYCLE START ***")
            print(f"Running: {os.path.basename(self.loaded_program_path)}")
            print("="*50)
            
            self.command.mode(linuxcnc.MODE_AUTO)
            self.command.wait_complete()
            self.command.auto(linuxcnc.AUTO_RUN, 0)
            
            print("✓ Program started")
            
        except Exception as e:
            print(f"ERROR: {e}")
    
    def pause_program(self):
        """Pause program execution"""
        try:
            self.command.auto(linuxcnc.AUTO_PAUSE)
            print("Program PAUSED")
        except Exception as e:
            print(f"Pause error: {e}")
    
    def stop_program(self):
        """Stop program execution"""
        try:
            self.command.abort()
            print("Program STOPPED")
        except Exception as e:
            print(f"Stop error: {e}")
    
    def execute_mdi(self):
        """
        Execute an MDI command robustly.

        Root causes fixed vs. the previous implementation:

        1. WRONG API — self.command.error() does not exist on linuxcnc.command.
           Fixed: use linuxcnc.error_channel().poll() instead.

        2. MODAL / INSTANT COMMANDS (G49, G54, G53, etc.) complete so fast that
           the interpreter never leaves INTERP_IDLE.  The old code used a fixed
           time.sleep(0.1) then checked interp_state, but for instant modals the
           interpreter is already idle again by then — causing false "did not
           execute" conclusions.
           Fixed: drain the error channel AFTER wait_complete() regardless of
           interp_state.  If no error is present the command succeeded.

        3. WAIT_COMPLETE TIMEOUT — the old code called wait_complete(1.0) after
           mode() but NOT after mdi(), so long-running commands (G0 moves, M6)
           could race.
           Fixed: call wait_complete() with a generous timeout after mdi() too.

        4. INTERPRETER NOT IDLE BEFORE SEND — if a previous command was still
           running, sending a new MDI command could corrupt state.
           Fixed: poll and confirm INTERP_IDLE before sending the new command.

        5. G10 L1 P0 — P0 is invalid for G10 L1 (P must be ≥ 1).  This is a
           G-code spec error, not a handler bug.  A clear message is printed.
           The pseudo-command interceptor explains this to the user instead of
           letting LinuxCNC emit a cryptic "P value out of range" error.
        """
        if not STATUS.machine_is_on():
            print("ERROR: Power is OFF! Click POWER ON first.")
            return

        # ── Advisory homing check (non-blocking) ─────────────────────────
        self.stat.poll()
        all_homed = all(self.stat.homed[i] == 1 for i in range(INFO.JOINT_COUNT))
        if not all_homed:
            print("\n" + "="*50)
            print("⚠ WARNING: NOT ALL AXES HOMED!")
            print("MDI commands may be rejected by LinuxCNC")
            print("Recommendation: Click HOME ALL first")
            print("="*50 + "\n")

        gcode_command = self.w.text_mdi_input.text().strip()
        if not gcode_command:
            print("ERROR: No command entered!")
            return

        # ── PSEUDO-COMMAND INTERCEPTOR ────────────────────────────────────
        # Intercept Grbl-style / convenience shortcuts before they reach the
        # LinuxCNC G-code interpreter (which would reject them).
        cmd_upper = gcode_command.upper().strip()
        if cmd_upper in ("$HOME", "HOME ALL", "HOMEALL"):
            print(f"\n[MDI intercepted '{gcode_command}' -> HOME ALL]")
            self.w.text_mdi_input.clear()
            self.home_all()
            return
        if cmd_upper in ("$HOME X", "HOME X"):
            print(f"\n[MDI intercepted '{gcode_command}' -> HOME X]")
            self.w.text_mdi_input.clear()
            self.home_x_axis()
            return
        if cmd_upper in ("$HOME Y", "HOME Y"):
            print(f"\n[MDI intercepted '{gcode_command}' -> HOME Y]")
            self.w.text_mdi_input.clear()
            self.home_y_axis()
            return
        if cmd_upper in ("$HOME Z", "HOME Z"):
            print(f"\n[MDI intercepted '{gcode_command}' -> HOME Z]")
            self.w.text_mdi_input.clear()
            self.home_z_axis()
            return
        # ── END PSEUDO-COMMAND INTERCEPTOR ───────────────────────────────

        print("\n" + "="*50)
        print(f"EXECUTING MDI: {gcode_command}")
        print("="*50)

        try:
            # ── Step 1: Abort any in-progress motion cleanly ──────────────
            # Only abort if the interpreter is NOT idle; avoids unnecessary
            # state disruption for G49/G54 and other pure modal commands.
            self.stat.poll()
            if self.stat.interp_state != linuxcnc.INTERP_IDLE:
                self.command.abort()
                # Give controller time to settle after abort
                deadline = time.time() + 2.0
                while time.time() < deadline:
                    self.stat.poll()
                    if self.stat.interp_state == linuxcnc.INTERP_IDLE:
                        break
                    time.sleep(0.02)

            # ── Step 2: Switch to MDI mode ────────────────────────────────
            self.command.mode(linuxcnc.MODE_MDI)
            # wait_complete() with timeout ensures the mode switch is ACK'd
            # by the task controller before we proceed.
            rc = self.command.wait_complete(3.0)
            if rc == linuxcnc.RCS_ERROR:
                print("✗ ERROR: mode switch to MDI returned RCS_ERROR")
                print("="*50 + "\n")
                return

            # ── Step 3: Confirm mode via stat ─────────────────────────────
            # Poll up to ~500 ms; mode switches are near-instant but the
            # NML bus can lag by a cycle or two.
            deadline = time.time() + 0.5
            while time.time() < deadline:
                self.stat.poll()
                if self.stat.task_mode == linuxcnc.MODE_MDI:
                    break
                time.sleep(0.02)
            if self.stat.task_mode != linuxcnc.MODE_MDI:
                print("✗ ERROR: Failed to confirm MDI mode!")
                print(f"  task_mode = {self.stat.task_mode}")
                print("="*50 + "\n")
                return

            # ── Step 4: Confirm interpreter is idle ───────────────────────
            # Modal commands (G49, G54, G53) are rejected if the interpreter
            # is busy with a previous block.
            deadline = time.time() + 1.0
            while time.time() < deadline:
                self.stat.poll()
                if self.stat.interp_state == linuxcnc.INTERP_IDLE:
                    break
                time.sleep(0.02)
            if self.stat.interp_state != linuxcnc.INTERP_IDLE:
                print("✗ ERROR: Interpreter is not idle — cannot send MDI command")
                print(f"  interp_state = {self.stat.interp_state}")
                print("="*50 + "\n")
                return

            # ── Step 5: Drain any stale errors before sending ─────────────
            # Prevents old errors from being mis-attributed to the new command.
            try:
                _ec = linuxcnc.error_channel()
                while True:
                    _stale = _ec.poll()
                    if not _stale:
                        break
            except Exception:
                pass

            # ── Step 6: Send the MDI command ──────────────────────────────
            self.command.mdi(gcode_command)

            # ── Step 7: Wait for completion ───────────────────────────────
            # wait_complete() blocks until the command finishes OR times out.
            # Timeout is 30 s — long enough for any normal milling move.
            # Modal-only commands (G49, G54, G53, G10 coord system) complete
            # in microseconds, so this returns almost immediately for them.
            rc = self.command.wait_complete(30.0)
            if rc == linuxcnc.RCS_ERROR:
                # RCS_ERROR on wait means the command was rejected by the
                # interpreter.  Read the error channel for the actual message.
                pass  # fall through to error channel check below

            # ── Step 8: Poll final state ──────────────────────────────────
            self.stat.poll()
            # Force immediate coolant UI sync — don't wait for next 100 ms tick
            try:
                self._last_coolant_state = None   # invalidate cache so update fires
                self._update_coolant_status()
            except Exception:
                pass

            # ── Step 9: Check error channel for interpreter errors ────────
            # This is the ONLY correct way to read LinuxCNC errors.
            # linuxcnc.command has NO .error() method — calling it raises
            # AttributeError: 'linuxcnc.command' object has no attribute 'error'
            cmd_failed = False
            try:
                ec = linuxcnc.error_channel()
                # Drain all pending messages; keep the last real error.
                last_error = None
                while True:
                    msg = ec.poll()
                    if not msg:
                        break
                    if msg[0] in (linuxcnc.NML_ERROR, linuxcnc.OPERATOR_ERROR):
                        last_error = msg[1]
                if last_error:
                    print(f"✗ LinuxCNC ERROR: {last_error}")
                    print("Common causes:")
                    print("  - Axes not homed (most modal commands still work unhomed)")
                    print("  - G10 L1 P0 is invalid — P must be ≥ 1 (tool number)")
                    print("  - Command exceeds soft limits")
                    print("  - Invalid G-code syntax")
                    print("="*50 + "\n")
                    cmd_failed = True
            except Exception as ec_ex:
                print(f"  (error channel unavailable: {ec_ex})")

            if cmd_failed:
                return

            # ── Step 10: Add to history and clear input ───────────────────
            current = self.w.text_mdi_history.toPlainText()
            if current:
                self.w.text_mdi_history.setPlainText(current + "\n" + gcode_command)
            else:
                self.w.text_mdi_history.setPlainText(gcode_command)
            scrollbar = self.w.text_mdi_history.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
            self.w.text_mdi_input.clear()

            print("✓ Command executed successfully")
            print("="*50 + "\n")

        except Exception as e:
            print(f"✗ MDI ERROR: {e}")
            print("="*50 + "\n")
    
    def clear_mdi(self):
        """Clear MDI history"""
        self.w.text_mdi_history.clear()
        self.w.text_mdi_input.clear()
        print("MDI history cleared")
    
    def set_jog_increment(self, increment):
        """Set jog increment"""
        if increment == "continuous":
            self.jog_mode = "continuous"
            self.jog_increment = 0
            print("Jog: CONTINUOUS")
        else:
            self.jog_mode = "increment"
            self.jog_increment = increment
            print(f"Jog: {increment} mm")
    
    def update_jog_velocity(self, value):
        """Update jog velocity"""
        self.jog_speed = value
        self.w.label_jog_2.setText(f"Jog Velocity: {value}mm/min")
    
    def toggle_estop(self):
        """Toggle E-stop"""
        if STATUS.estop_is_clear():
            print("E-Stop ACTIVATED")
            ACTION.SET_ESTOP_STATE(True)
        else:
            print("E-Stop CLEARED")
            ACTION.SET_ESTOP_STATE(False)
    
    def toggle_power(self):
        """Toggle power"""
        if STATUS.machine_is_on():
            print("Machine POWER OFF")
            ACTION.SET_MACHINE_STATE(False)
        else:
            if not STATUS.estop_is_clear():
                print("ERROR: Clear E-stop first!")
                return
            print("Machine POWER ON")
            ACTION.SET_MACHINE_STATE(True)
    
    def home_all(self):
        """Home all axes"""
        if not STATUS.estop_is_clear():
            print("ERROR: Clear E-stop first!")
            return
        if not STATUS.machine_is_on():
            print("ERROR: Power OFF!")
            return
        
        print("\n*** HOMING ALL AXES ***")
        try:
            self.stat.poll()
            self.command.mode(linuxcnc.MODE_MANUAL)
            self.command.wait_complete()
            
            num_joints = INFO.JOINT_COUNT
            for joint_num in range(num_joints):
                if self.stat.homed[joint_num] == 1:
                    self.command.unhome(joint_num)
            
            self.command.wait_complete()
            
            for joint_num in range(num_joints):
                self.command.home(joint_num)
            
            print("✓ Homing complete - DRO shows 0.000")
            print("All axes (X, Y, Z) are now homed")
        except Exception as e:
            print(f"Homing error: {e}")
        print("="*25 + "\n")
    
    # — ADDED FOR AXIS HOMING BUTTONS —
    def home_x_axis(self):
        """Home X axis using dynamically assigned joint"""
        if not STATUS.estop_is_clear():
            print("ERROR: Clear E-stop first!")
            return
        if not STATUS.machine_is_on():
            print("ERROR: Power OFF!")
            return
        
        print(f"\n*** HOMING X AXIS (Joint {self.home_x_joint}) ***")
        try:
            self.stat.poll()
            self.command.mode(linuxcnc.MODE_MANUAL)
            self.command.wait_complete()
            
            # Unhome if already homed
            if self.stat.homed[self.home_x_joint] == 1:
                self.command.unhome(self.home_x_joint)
                self.command.wait_complete()
            
            # Home assigned joint
            self.command.home(self.home_x_joint)
            
            print("✓ X axis homing initiated")
        except Exception as e:
            print(f"X axis homing error: {e}")
        print("="*25 + "\n")
    
    def home_y_axis(self):
        """Home Y axis using dynamically assigned joint"""
        if not STATUS.estop_is_clear():
            print("ERROR: Clear E-stop first!")
            return
        if not STATUS.machine_is_on():
            print("ERROR: Power OFF!")
            return
        
        print(f"\n*** HOMING Y AXIS (Joint {self.home_y_joint}) ***")
        try:
            self.stat.poll()
            self.command.mode(linuxcnc.MODE_MANUAL)
            self.command.wait_complete()
            
            # Unhome if already homed
            if self.stat.homed[self.home_y_joint] == 1:
                self.command.unhome(self.home_y_joint)
                self.command.wait_complete()
            
            # Home assigned joint
            self.command.home(self.home_y_joint)
            
            print("✓ Y axis homing initiated")
        except Exception as e:
            print(f"Y axis homing error: {e}")
        print("="*25 + "\n")
    
    def home_z_axis(self):
        """Home Z axis using dynamically assigned joint"""
        if not STATUS.estop_is_clear():
            print("ERROR: Clear E-stop first!")
            return
        if not STATUS.machine_is_on():
            print("ERROR: Power OFF!")
            return
        
        print(f"\n*** HOMING Z AXIS (Joint {self.home_z_joint}) ***")
        try:
            self.stat.poll()
            self.command.mode(linuxcnc.MODE_MANUAL)
            self.command.wait_complete()
            
            # Unhome if already homed
            if self.stat.homed[self.home_z_joint] == 1:
                self.command.unhome(self.home_z_joint)
                self.command.wait_complete()
            
            # Home assigned joint
            self.command.home(self.home_z_joint)
            
            print("✓ Z axis homing initiated")
        except Exception as e:
            print(f"Z axis homing error: {e}")
        print("="*25 + "\n")
    # — END ADDED FOR AXIS HOMING BUTTONS —
    
    # — ADDED: DYNAMIC HOME BUTTON BINDING —
    def open_joint_assignment_dialog(self):
        """Open dialog to reassign joints to home buttons"""
        # Get current mappings
        current_mappings = {
            'x': self.home_x_joint,
            'y': self.home_y_joint,
            'z': self.home_z_joint
        }
        
        # Get joint count from INFO
        joint_count = INFO.JOINT_COUNT
        
        # Create and show dialog
        dialog = JointAssignmentDialog(self.w, current_mappings, joint_count)
        
        # Execute dialog and get result
        if dialog.exec_():
            # User confirmed - apply new mappings
            new_mappings = dialog.get_mappings()
            if new_mappings:
                self.home_x_joint = new_mappings['x']
                self.home_y_joint = new_mappings['y']
                self.home_z_joint = new_mappings['z']
                
                print("\n*** JOINT ASSIGNMENT UPDATED ***")
                print(f"HOME X → Joint {self.home_x_joint}")
                print(f"HOME Y → Joint {self.home_y_joint}")
                print(f"HOME Z → Joint {self.home_z_joint}")
                print("="*35 + "\n")
        else:
            print("Joint assignment cancelled")
    # — END ADDED: DYNAMIC HOME BUTTON BINDING —
    
    def jog_joint(self, joint_num, direction):
        """Start jogging"""
        if self.current_mode != "MANUAL":
            return
        
        if not STATUS.machine_is_on() or not STATUS.estop_is_clear():
            return
        
        # Convert mm/min to mm/sec for LinuxCNC
        speed_per_sec = self.jog_speed / 60.0
        
        if self.jog_mode == "continuous":
            ACTION.JOG(joint_num, direction, speed_per_sec)
        else:
            ACTION.JOG(joint_num, direction, speed_per_sec, self.jog_increment)
    
    def jog_stop(self, joint_num):
        """Stop jogging"""
        if self.jog_mode == "continuous":
            ACTION.JOG(joint_num, 0, 0)
    
    def update_spindle_speed_display(self, value):
        """Update spindle speed"""
        self.spindle_speed = value
        self.w.label_spindle_speed.setText(f"Speed: {value} RPM")
    
    def spindle_forward(self):
        """Spindle forward"""
        if not STATUS.machine_is_on():
            return
        print(f"Spindle FWD {self.spindle_speed} RPM")
        ACTION.SET_SPINDLE_ROTATION(1, self.spindle_speed)
    
    def spindle_stop(self):
        """Spindle stop"""
        print("Spindle STOP")
        ACTION.SET_SPINDLE_ROTATION(0, 0)
    
    def spindle_reverse(self):
        """Spindle reverse"""
        if not STATUS.machine_is_on():
            return
        print(f"Spindle REV {self.spindle_speed} RPM")
        ACTION.SET_SPINDLE_ROTATION(-1, self.spindle_speed)

    # ── COOLING CONTROL ───────────────────────────────────────────────────────
    def _send_coolant_mdi(self, gcode):
        """
        Send M8 or M9 via MDI then restore the previous mode.
        Works in MANUAL, MDI, and AUTO modes.
        AUTO: aborts any running program first (LinuxCNC cannot send MDI
        while a program is executing — stop is mandatory before M8/M9).
        """
        if not STATUS.machine_is_on():
            print("COOLANT: Machine power is OFF — ignored")
            return
        try:
            self.stat.poll()
            prev_mode = self.stat.task_mode

            # If AUTO is running, stop before switching to MDI
            if self.is_auto_running():
                self.command.abort()
                deadline = time.time() + 2.0
                while time.time() < deadline:
                    self.stat.poll()
                    if self.stat.interp_state == linuxcnc.INTERP_IDLE:
                        break
                    time.sleep(0.02)

            self.command.mode(linuxcnc.MODE_MDI)
            self.command.wait_complete(2.0)
            self.command.mdi(gcode)
            self.command.wait_complete(5.0)

            # Restore previous mode
            if prev_mode == linuxcnc.MODE_AUTO:
                self.command.mode(linuxcnc.MODE_AUTO)
            elif prev_mode == linuxcnc.MODE_MANUAL:
                self.command.mode(linuxcnc.MODE_MANUAL)
            # (MDI stays in MDI)
            self.command.wait_complete(1.0)
            print(f"✓ Coolant command sent: {gcode}")
        except Exception as e:
            print(f"Coolant command error ({gcode}): {e}")

    def coolant_toggle(self):
        """Single coolant toggle — reads live stat to decide M8 or M9."""
        try:
            self.stat.poll()
            coolant_on = bool(self.stat.flood or self.stat.mist)
        except Exception:
            coolant_on = False
        if coolant_on:
            self._send_coolant_mdi("M9")
        else:
            self._send_coolant_mdi("M8")
        # Invalidate cache so the next periodic_update() repaints immediately
        self._last_coolant_state = None

    # ── Stylesheet constants for single coolant toggle button ──────────────
    _COOLANT_BTN_ON_STYLE = (
        "QPushButton { background-color: #27ae60; color: white;"
        " border: 3px solid #ffffff; font-weight: bold;"
        " border-radius: 4px; font-size: 10pt; }"
        "QPushButton:hover { border-color: #ccffcc; }"
        "QPushButton:pressed { background-color: #1e8449; padding-top: 7px; padding-left: 7px; }"
    )
    _COOLANT_BTN_OFF_STYLE = (
        "QPushButton { background-color: #c0392b; color: white;"
        " border: 3px solid #ffffff; font-weight: bold;"
        " border-radius: 4px; font-size: 10pt; }"
        "QPushButton:hover { border-color: #ffcccc; }"
        "QPushButton:pressed { background-color: #943126; padding-top: 7px; padding-left: 7px; }"
    )

    def _update_coolant_status(self):
        """
        Reads stat.flood / stat.mist (set by M8/M9 from any source: button,
        MDI, or running G-code program) and updates the single toggle button.

        Called from periodic_update() every 100 ms.
        Change-detection: UI is only repainted when state actually changes.

          Coolant ON  → btn_coolant_toggle: bright GREEN, text "COOLANT ON"
          Coolant OFF → btn_coolant_toggle: bright RED,   text "COOLANT OFF"
        """
        self.stat.poll()
        coolant_on = bool(self.stat.flood or self.stat.mist)

        if coolant_on == self._last_coolant_state:
            return  # no change — skip all UI work

        self._last_coolant_state = coolant_on

        if coolant_on:
            try:
                self.w.lbl_cooling_status.setText("Coolant: ON")
                self.w.lbl_cooling_status.setStyleSheet(
                    "color: #00ff88; font-weight: bold; font-size: 9pt;"
                )
            except Exception:
                pass
            try:
                self.w.btn_coolant_toggle.setText("COOLANT ON")
                self.w.btn_coolant_toggle.setStyleSheet(self._COOLANT_BTN_ON_STYLE)
            except Exception:
                pass
        else:
            try:
                self.w.lbl_cooling_status.setText("Coolant: OFF")
                self.w.lbl_cooling_status.setStyleSheet(
                    "color: #aaaaaa; font-weight: bold; font-size: 9pt;"
                )
            except Exception:
                pass
            try:
                self.w.btn_coolant_toggle.setText("COOLANT OFF")
                self.w.btn_coolant_toggle.setStyleSheet(self._COOLANT_BTN_OFF_STYLE)
            except Exception:
                pass
    # ── END COOLING CONTROL ───────────────────────────────────────────────────

    def update_feedrate_override(self, value):
        """Feed rate override"""
        self.w.label_feedrate.setText(f"{value}%")
        ACTION.SET_FEED_RATE(value / 100.0)
    
    def update_rapid_override(self, value):
        """Rapid override"""
        self.w.label_rapidrate.setText(f"{value}%")
        ACTION.SET_RAPID_RATE(value / 100.0)

    # ═══════════════════════════════════════════════════════════════════════
    # — ADDED: TOOL MANAGEMENT —
    # ═══════════════════════════════════════════════════════════════════════

    def setup_tool_management(self):
        """
        Initialize tool management panel.
        - Resolves tool table file path from INI (never hardcoded).
        - Connects all tool button signals.
        - Loads tool table on startup.
        - Hides panel by default.
        """
        print("\n*** TOOL MANAGEMENT INIT ***")

        # ── Resolve tool file path from INI ──────────────────────────────
        # ROOT CAUSE FIX: INFO.INI_FILENAME can be None at this stage because
        # the Info() singleton populates lazily in QtVCP. Using it too early
        # caused linuxcnc.ini(None) to fail silently, leaving tool_file_path=None
        # and producing an empty table.
        # SOLUTION: os.environ['INI_FILE_NAME'] is set by LinuxCNC before QtVCP
        # starts and is ALWAYS reliable. INFO is kept as a secondary fallback.
        self.tool_file_path = None
        try:
            # Primary: environment variable (guaranteed by LinuxCNC runtime)
            ini_file = os.environ.get('INI_FILE_NAME', '')
            # Secondary: INFO object (may be populated by this point)
            if not ini_file:
                try:
                    ini_file = INFO.INI_FILENAME or ''
                except Exception:
                    ini_file = ''

            if ini_file and os.path.isfile(ini_file):
                ini_obj = linuxcnc.ini(ini_file)
                raw_path = ini_obj.find("EMCIO", "TOOL_TABLE") or ""
                if raw_path:
                    if os.path.isabs(raw_path):
                        candidate = raw_path
                    else:
                        # Relative path → resolve against INI file directory
                        ini_dir = os.path.dirname(os.path.abspath(ini_file))
                        candidate = os.path.join(ini_dir, raw_path)
                    if os.path.isfile(candidate):
                        self.tool_file_path = candidate
                        print(f"✓ Tool table resolved: {self.tool_file_path}")
                    else:
                        print(f"⚠ Tool table path not found at: {candidate}")
                else:
                    print("⚠ TOOL_TABLE key missing from [EMCIO] in INI")
            else:
                print(f"⚠ INI file not accessible: '{ini_file}'")
        except Exception as e:
            print(f"Tool table path resolution error: {e}")
            self.tool_file_path = None

        # ── Configure table widget columns ───────────────────────────────
        try:
            tbl = self.w.table_tools
            tbl.setColumnCount(7)
            tbl.setHorizontalHeaderLabels(
                ["T#", "Pocket", "X Off", "Y Off", "Z Off", "Diam", "Comment"]
            )
            # Column widths (proportional, total ~474px)
            for col, w in enumerate([38, 46, 60, 60, 60, 50, 160]):
                tbl.setColumnWidth(col, w)
            tbl.horizontalHeader().setStretchLastSection(True)
            tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
            tbl.setSelectionMode(QAbstractItemView.SingleSelection)
            tbl.verticalHeader().setDefaultSectionSize(24)
            tbl.verticalHeader().hide()
        except Exception as e:
            print(f"Table config error: {e}")

        # ── Connect TOOL button signals ───────────────────────────────────
        try:
            self.w.btn_tool_mgmt.clicked.connect(self.toggle_tool_panel)
            self.w.btn_tool_close.clicked.connect(self.hide_tool_panel)
            self.w.btn_tool_add.clicked.connect(self.tool_add_row)
            self.w.btn_tool_delete.clicked.connect(self.tool_delete_row)
            self.w.btn_tool_reload.clicked.connect(self.tool_reload_table)
            self.w.btn_tool_apply.clicked.connect(self.tool_apply_changes)
            self.w.btn_tool_select.clicked.connect(self.tool_select)
            self.w.btn_tool_change.clicked.connect(self.tool_change_m6)
            self.w.btn_tool_touch_z.clicked.connect(self.tool_touch_off_z)
            self.w.btn_tool_update_offset.clicked.connect(self.tool_update_z_offset)
            self.w.btn_tool_load.clicked.connect(self.tool_load)
            self.w.btn_tool_unload.clicked.connect(self.tool_unload)
            # Track edits for dirty-flag
            self.w.table_tools.itemChanged.connect(self._on_tool_table_edited)
            print("✓ Tool button signals connected")
        except Exception as e:
            print(f"Tool signal error: {e}")

        # ── Ensure panel starts hidden ────────────────────────────────────
        try:
            self.w.frame_tool_panel.setVisible(False)
            self.w.btn_tool_mgmt.setChecked(False)
        except Exception as e:
            print(f"Tool panel hide error: {e}")

        # ── Load tool table on startup ────────────────────────────────────
        self.tool_reload_table()
        print("="*35 + "\n")

    # ────────────────────────────────────────────────────────────────────
    # Panel Visibility
    # ────────────────────────────────────────────────────────────────────

    def _reposition_tool_panel(self):
        """
        Resize and position frame_tool_panel so it covers the gcode_viewer area.
        Called on every window resize and when the panel is shown.
        """
        try:
            gv = self.w.gcode_viewer
            fp = self.w.frame_tool_panel
            # Map gcode_viewer top-left to centralwidget coordinates
            pos = gv.mapTo(self.w.centralWidget(), gv.rect().topLeft())
            # Make overlay same size as gcode_viewer widget
            fp.setGeometry(pos.x(), pos.y(), gv.width(), gv.height())
        except Exception:
            pass

    def toggle_tool_panel(self):
        """Toggle tool management panel visibility"""
        if self.tool_panel_visible:
            self.hide_tool_panel()
        else:
            self.show_tool_panel()

    def show_tool_panel(self):
        """Show tool panel, overlay gcode viewer, refresh table"""
        self._reposition_tool_panel()   # ← ensure correct position/size first
        self.tool_panel_visible = True
        self.w.frame_tool_panel.setVisible(True)
        self.w.frame_tool_panel.raise_()
        self.w.btn_tool_mgmt.setChecked(True)
        # Refresh status bar and table whenever panel opens
        self.tool_reload_table()
        self._update_tool_status_bar()
        print("Tool Management panel OPEN")

    def hide_tool_panel(self):
        """Hide tool panel, restore gcode viewer"""
        # Warn if there are unsaved changes
        if self.tool_table_modified:
            reply = QMessageBox.question(
                self.w,
                "Unsaved Changes",
                "Tool table has unsaved changes.\nClose anyway?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                return
        self.tool_panel_visible = False
        self.w.frame_tool_panel.setVisible(False)
        self.w.btn_tool_mgmt.setChecked(False)
        self.tool_table_modified = False
        print("Tool Management panel CLOSED")

    # ────────────────────────────────────────────────────────────────────
    # Tool File Parsing
    # ────────────────────────────────────────────────────────────────────

    def _parse_tool_file(self):
        """
        Parse the tool table using a two-source merge strategy:

        SOURCE 1 — linuxcnc.stat().tool_table  (primary, authoritative)
            Always reflects what the CONTROLLER actually has loaded.
            Provides: tool id (T#), all offsets (X/Y/Z/D etc.)
            Does NOT provide: pocket number, comment.

        SOURCE 2 — tool.tbl file on disk  (secondary, metadata)
            Provides: pocket number, comment (not in stat).
            May lag stat by one 'Apply Changes' cycle.

        Merge: For every tool in the file, look up its live offset data
        from stat. Display stat offsets so edits post-G10 are visible
        immediately without needing a file reload.

        Falls back to file-only parsing if stat is unavailable.
        """
        # ── Step 1: Parse file for pocket + comment metadata ─────────────
        file_tools = {}   # keyed by T number (int)
        if self.tool_file_path and os.path.isfile(self.tool_file_path):
            try:
                with open(self.tool_file_path, 'r') as fh:
                    for raw_line in fh:
                        line = raw_line.strip()
                        if not line:
                            continue
                        comment = ""
                        if ';' in line:
                            parts = line.split(';', 1)
                            line = parts[0].strip()
                            comment = parts[1].strip()
                        if not line:
                            continue
                        tokens = line.upper().split()
                        entry = {'T': 0, 'P': 0, 'X': 0.0, 'Y': 0.0,
                                 'Z': 0.0, 'D': 0.0, 'comment': comment}
                        for tok in tokens:
                            for key in ('T', 'P', 'X', 'Y', 'Z', 'D'):
                                if tok.startswith(key) and len(tok) > len(key):
                                    try:
                                        entry[key] = int(tok[len(key):]) if key in ('T', 'P') else float(tok[len(key):])
                                    except ValueError:
                                        pass
                                    break
                        t_num = entry['T']
                        if t_num > 0:   # skip T0 (no-tool placeholder)
                            file_tools[t_num] = entry
            except Exception as e:
                print(f"Tool file parse error: {e}")

        # ── Step 2: Read live offsets from stat.tool_table ────────────────
        # stat.tool_table is a tuple of tool_result objects, one per tool.
        # Each has: .id, .xoffset, .yoffset, .zoffset, .diameter, .comment
        # This is what the controller ACTUALLY has — authoritative for offsets.
        stat_tools = {}   # keyed by T number (int)
        try:
            self.stat.poll()
            for t in self.stat.tool_table:
                tid = t.id
                if tid == 0:
                    continue  # T0 = no tool loaded
                stat_tools[tid] = {
                    'T': tid,
                    'X': t.xoffset,
                    'Y': t.yoffset,
                    'Z': t.zoffset,
                    'D': t.diameter,
                }
        except Exception as e:
            print(f"stat.tool_table read error (using file data only): {e}")

        # ── Step 3: Merge — build final list ─────────────────────────────
        # Use all tool numbers seen in EITHER source.
        # Offsets come from stat (live), pocket+comment from file.
        all_t_nums = sorted(set(list(file_tools.keys()) + list(stat_tools.keys())))
        merged = []
        for t_num in all_t_nums:
            f = file_tools.get(t_num, {})
            s = stat_tools.get(t_num, {})
            merged.append({
                'T':       str(t_num),
                'P':       str(f.get('P', t_num)),   # pocket from file
                'X':       f"{s.get('X', f.get('X', 0.0)):.4f}",
                'Y':       f"{s.get('Y', f.get('Y', 0.0)):.4f}",
                'Z':       f"{s.get('Z', f.get('Z', 0.0)):.4f}",
                'D':       f"{s.get('D', f.get('D', 0.0)):.4f}",
                'comment': f.get('comment', ''),
            })

        if not merged:
            print("⚠ No tools found in file or stat. Check tool_file_path and LinuxCNC state.")
        return merged

    def _write_tool_file(self, tools):
        """
        Write edited tool table back to the tool.tbl file.

        Format follows the LinuxCNC standard:
            T{n} P{p} X{x} Y{y} Z{z} D{d} ;comment
        All offset fields are written explicitly so LinuxCNC reads them
        correctly. Pocket must match the T number for random-tool-changer
        emulators; for fixed-pocket machines it is already correct.
        After writing, call command.load_tool_table() to push changes
        into the controller without a restart.
        """
        if not self.tool_file_path:
            print("ERROR: No tool file path set — cannot write")
            return False
        try:
            lines = []
            for t in tools:
                try:
                    tn = int(t.get('T', '0'))
                    p  = int(t.get('P', '0'))
                    x  = float(t.get('X', '0.0'))
                    y  = float(t.get('Y', '0.0'))
                    z  = float(t.get('Z', '0.0'))
                    d  = float(t.get('D', '0.0'))
                    c  = t.get('comment', '').strip()
                    line = f"T{tn} P{p} X{x:.4f} Y{y:.4f} Z{z:.4f} D{d:.4f}"
                    if c:
                        line += f" ;{c}"
                    lines.append(line)
                except (ValueError, TypeError) as e:
                    print(f"Skipping malformed tool row: {t} ({e})")
            with open(self.tool_file_path, 'w') as fh:
                fh.write('\n'.join(lines) + '\n')
            print(f"✓ Wrote {len(lines)} tools to {self.tool_file_path}")
            return True
        except Exception as e:
            print(f"Tool file write error: {e}")
            return False

    # ────────────────────────────────────────────────────────────────────
    # Table Population
    # ────────────────────────────────────────────────────────────────────

    def tool_reload_table(self):
        """
        Repopulate QTableWidget from the two-source merge in _parse_tool_file().
        Offsets come from stat.tool_table (live), pocket/comment from the file.
        Signals are blocked during population to suppress false dirty-flags.
        """
        try:
            tbl = self.w.table_tools
            tbl.blockSignals(True)
            tbl.setRowCount(0)
            tools = self._parse_tool_file()
            blue = QColor('#00aaff')
            for row, t in enumerate(tools):
                tbl.insertRow(row)
                vals = [
                    t.get('T', '0'),       # col 0: T#
                    t.get('P', '0'),       # col 1: Pocket
                    t.get('X', '0.0000'),  # col 2: X offset
                    t.get('Y', '0.0000'),  # col 3: Y offset
                    t.get('Z', '0.0000'),  # col 4: Z offset
                    t.get('D', '0.0000'),  # col 5: Diameter
                    t.get('comment', ''),   # col 6: Comment
                ]
                for col, val in enumerate(vals):
                    item = QTableWidgetItem(str(val))
                    if col in (0, 1):
                        # T# and Pocket: coloured for visual distinction
                        item.setForeground(blue)
                    tbl.setItem(row, col, item)
            tbl.blockSignals(False)
            self.tool_table_modified = False
            self._update_tool_status_bar()
            src = "stat+file" if tools else "no data"
            print(f"✓ Tool table loaded: {len(tools)} tools  [{src}]"
                  + (f"  path: {self.tool_file_path}" if self.tool_file_path else "  (no path resolved)"))
        except Exception as e:
            print(f"Tool reload error: {e}")
            try:
                self.w.table_tools.blockSignals(False)
            except Exception:
                pass

    def _on_tool_table_edited(self, item):
        """Called when user edits any table cell — mark as modified"""
        self.tool_table_modified = True

    def _update_tool_status_bar(self):
        """
        Update status bar from stat.tool_table (live controller data).
        stat.tool_in_spindle gives the active T number.
        stat.tool_table entries give live offsets for that tool.
        Pocket and comment are looked up from the file (not in stat).
        """
        try:
            self.stat.poll()
            tool_num = self.stat.tool_in_spindle   # int, 0 = no tool
            d_str = "-"
            z_str = "-"
            p_str = "-"
            cmt_str = ""

            # ── Offset data from stat (live, controller-authoritative) ──
            try:
                for t in self.stat.tool_table:
                    if t.id == tool_num and tool_num != 0:
                        d_str = f"{t.diameter:.4f}"
                        z_str = f"{t.zoffset:.4f}"
                        break
            except Exception:
                pass

            # ── Pocket + comment from file (metadata not in stat) ──────
            if self.tool_file_path and os.path.isfile(self.tool_file_path):
                try:
                    with open(self.tool_file_path, 'r') as fh:
                        for line in fh:
                            line = line.strip()
                            comment = ""
                            if ';' in line:
                                line, comment = line.split(';', 1)
                                comment = comment.strip()
                            tokens = line.upper().split()
                            t_val = p_val = 0
                            for tok in tokens:
                                if tok.startswith('T') and len(tok) > 1:
                                    try: t_val = int(tok[1:])
                                    except ValueError: pass
                                elif tok.startswith('P') and len(tok) > 1:
                                    try: p_val = int(tok[1:])
                                    except ValueError: pass
                            if t_val == tool_num and tool_num != 0:
                                p_str = str(p_val)
                                cmt_str = comment
                                break
                except Exception:
                    pass

            if tool_num == 0:
                self.w.lbl_tool_status.setText(
                    "Active Tool: None  |  No tool in spindle"
                )
            else:
                self.w.lbl_tool_status.setText(
                    f"Active Tool: T{tool_num}  |  Pocket: {p_str}  |  "
                    f"Diameter: {d_str}  |  Z Offset: {z_str}"
                    + (f"  |  {cmt_str}" if cmt_str else "")
                )
        except Exception as e:
            try:
                self.w.lbl_tool_status.setText("Status unavailable")
            except Exception:
                pass

    # ────────────────────────────────────────────────────────────────────
    # Table Action Handlers
    # ────────────────────────────────────────────────────────────────────

    def _collect_table_tools(self):
        """Read all rows from the QTableWidget and return list of dicts"""
        tbl = self.w.table_tools
        tools = []
        for row in range(tbl.rowCount()):
            def cell(c):
                item = tbl.item(row, c)
                return item.text().strip() if item else ''
            tools.append({
                'T':       cell(0),
                'P':       cell(1),
                'X':       cell(2),
                'Y':       cell(3),
                'Z':       cell(4),
                'D':       cell(5),
                'comment': cell(6),
            })
        return tools

    def tool_add_row(self):
        """Add a new blank tool row at the bottom of the table"""
        tbl = self.w.table_tools
        tbl.blockSignals(True)
        row = tbl.rowCount()
        tbl.insertRow(row)
        # Auto-assign next tool number
        next_t = row + 1
        next_p = row + 1
        defaults = [str(next_t), str(next_p), '0.0', '0.0', '0.0', '0.0', '']
        for col, val in enumerate(defaults):
            item = QTableWidgetItem(val)
            tbl.setItem(row, col, item)
        tbl.blockSignals(False)
        tbl.selectRow(row)
        self.tool_table_modified = True
        print(f"✓ Tool row added: T{next_t}")

    def tool_delete_row(self):
        """Delete the currently selected tool row"""
        tbl = self.w.table_tools
        row = tbl.currentRow()
        if row < 0:
            QMessageBox.warning(self.w, "No Selection", "Select a tool row to delete.")
            return
        t_item = tbl.item(row, 0)
        t_num = t_item.text() if t_item else '?'
        reply = QMessageBox.question(
            self.w,
            "Delete Tool",
            f"Delete T{t_num} from the table?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            tbl.removeRow(row)
            self.tool_table_modified = True
            print(f"✓ Tool T{t_num} deleted")

    def tool_apply_changes(self):
        """
        Write edited tool table back to file and reload LinuxCNC tool data.
        This calls 'G10 L1' reload sequence via the load_tool_table command.
        """
        tools = self._collect_table_tools()
        if not tools:
            QMessageBox.warning(self.w, "Empty Table", "No tools to save.")
            return
        # Validate: tool numbers must be integers
        for t in tools:
            try:
                int(t['T'])
                int(t['P'])
            except ValueError:
                QMessageBox.critical(
                    self.w,
                    "Invalid Data",
                    f"Tool# and Pocket must be integers. Check row T{t['T']}."
                )
                return
        if self._write_tool_file(tools):
            # ── Push updated file into LinuxCNC controller ────────────────
            # command.load_tool_table() reads the file we just wrote and
            # updates the controller's internal tool data without a restart.
            # stat.tool_table will reflect the new values on next poll.
            reload_ok = False
            try:
                self.command.load_tool_table()
                reload_ok = True
                print("✓ LinuxCNC tool table reloaded via command.load_tool_table()")
            except AttributeError:
                # Older LinuxCNC versions may not have load_tool_table()
                print("⚠ command.load_tool_table() not available — trying MDI fallback")
                try:
                    if STATUS.machine_is_on():
                        self.command.mode(linuxcnc.MODE_MDI)
                        self.command.wait_complete()
                        # G10 L1 P0 triggers a tool table reload in the interpreter
                        self.command.mdi("G10 L1 P0")
                        self.command.wait_complete()
                        self.command.mode(linuxcnc.MODE_MANUAL)
                        reload_ok = True
                        print("✓ Tool table reloaded via G10 L1 P0 MDI fallback")
                except Exception as mdi_e:
                    print(f"MDI fallback error: {mdi_e}")
            except Exception as e:
                print(f"load_tool_table() error: {e}")

            self.tool_table_modified = False
            # Give controller one cycle to process the reload before repopulating
            QTimer.singleShot(200, self.tool_reload_table)
            self._update_tool_status_bar()
            msg = "Tool table saved and reloaded." if reload_ok else \
                  "Tool table saved. Reload into controller may be incomplete."
            QMessageBox.information(self.w, "Saved", msg)
            print("✓ Tool table apply complete")
        else:
            QMessageBox.critical(self.w, "Save Error", "Could not write tool table file.")

    # ────────────────────────────────────────────────────────────────────
    # Tool Control Handlers
    # ────────────────────────────────────────────────────────────────────

    def _get_selected_tool_num(self):
        """Return tool number (int) of currently selected table row, or None"""
        tbl = self.w.table_tools
        row = tbl.currentRow()
        if row < 0:
            return None
        item = tbl.item(row, 0)
        if not item:
            return None
        try:
            return int(item.text().strip())
        except ValueError:
            return None

    def tool_select(self):
        """
        Issue Tn to pre-select the chosen tool (tool prepare signal).
        Does NOT load it into spindle — that requires M6.
        """
        t_num = self._get_selected_tool_num()
        if t_num is None:
            QMessageBox.warning(self.w, "No Tool Selected", "Select a tool row first.")
            return
        if not STATUS.machine_is_on():
            QMessageBox.warning(self.w, "Machine Off", "Turn machine power ON first.")
            return
        try:
            self.command.mode(linuxcnc.MODE_MDI)
            self.command.wait_complete()
            self.command.mdi(f"T{t_num}")
            self.command.wait_complete()
            self.command.mode(linuxcnc.MODE_MANUAL)
            self._update_tool_status_bar()
            print(f"✓ Tool T{t_num} selected (prepared)")
        except Exception as e:
            print(f"Tool select error: {e}")

    def tool_change_m6(self):
        """
        Execute T{n} M6 to perform a tool change for the selected tool.
        Machine must be on and homed.
        """
        t_num = self._get_selected_tool_num()
        if t_num is None:
            QMessageBox.warning(self.w, "No Tool Selected", "Select a tool row first.")
            return
        if not STATUS.machine_is_on():
            QMessageBox.warning(self.w, "Machine Off", "Turn machine power ON first.")
            return
        # Check homing
        try:
            self.stat.poll()
            all_homed = all(self.stat.homed[i] == 1 for i in range(INFO.JOINT_COUNT))
            if not all_homed:
                reply = QMessageBox.question(
                    self.w,
                    "Not Homed",
                    "Not all axes are homed.\nProceed with tool change anyway?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                if reply == QMessageBox.No:
                    return
        except:
            pass
        try:
            print(f"\n*** TOOL CHANGE: T{t_num} M6 ***")
            self.command.mode(linuxcnc.MODE_MDI)
            self.command.wait_complete()
            self.command.mdi(f"T{t_num} M6")
            self.command.wait_complete()
            self.command.mode(linuxcnc.MODE_MANUAL)
            self._update_tool_status_bar()
            print(f"✓ Tool change to T{t_num} complete")
            print("="*35 + "\n")
        except Exception as e:
            print(f"Tool change error: {e}")

    def tool_touch_off_z(self):
        """
        Touch off Z axis to the value in spin_touch_z.
        Issues G10 L10 P{tool} Z{value} — sets tool Z offset so that
        current machine position corresponds to the given work Z.
        Works in Manual mode (machine must be on and homed).
        """
        if not STATUS.machine_is_on():
            QMessageBox.warning(self.w, "Machine Off", "Turn machine power ON first.")
            return
        try:
            self.stat.poll()
            tool_num = self.stat.tool_in_spindle
        except:
            tool_num = 0
        if tool_num == 0:
            QMessageBox.warning(
                self.w,
                "No Active Tool",
                "Load a tool first (T{n} M6) before touching off."
            )
            return
        try:
            z_val = self.w.spin_touch_z.value()
        except:
            z_val = 0.0
        reply = QMessageBox.question(
            self.w,
            "Touch Off Z",
            f"Set Z offset for T{tool_num} to {z_val:.4f}?\n"
            f"(G10 L10 P{tool_num} Z{z_val:.4f})",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        try:
            print(f"\n*** TOUCH OFF Z: T{tool_num} Z={z_val:.4f} ***")
            self.command.mode(linuxcnc.MODE_MDI)
            self.command.wait_complete()
            # G10 L10: set tool offset using current position as reference
            self.command.mdi(f"G10 L10 P{tool_num} Z{z_val:.4f}")
            self.command.wait_complete()
            self.command.mode(linuxcnc.MODE_MANUAL)
            # Reload tool table to pick up new offset
            self.tool_reload_table()
            self._update_tool_status_bar()
            print(f"✓ Z touch-off complete: T{tool_num} Z={z_val:.4f}")
            print("="*35 + "\n")
        except Exception as e:
            print(f"Touch off Z error: {e}")

    def tool_update_z_offset(self):
        """
        Update Z offset for selected tool row using G10 L1 (direct offset entry).
        Reads Z offset value from the selected table row's Z column.
        """
        if not STATUS.machine_is_on():
            QMessageBox.warning(self.w, "Machine Off", "Turn machine power ON first.")
            return
        t_num = self._get_selected_tool_num()
        if t_num is None:
            QMessageBox.warning(self.w, "No Tool Selected", "Select a tool row first.")
            return
        tbl = self.w.table_tools
        row = tbl.currentRow()
        z_item = tbl.item(row, 4)  # Column 4 = Z offset
        if not z_item:
            return
        try:
            z_val = float(z_item.text().strip())
        except ValueError:
            QMessageBox.critical(self.w, "Invalid Z", "Z offset must be a valid number.")
            return
        reply = QMessageBox.question(
            self.w,
            "Update Z Offset",
            f"Set T{t_num} Z offset to {z_val:.4f} mm?\n(G10 L1 P{t_num} Z{z_val:.4f})",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        try:
            print(f"\n*** UPDATE Z OFFSET: T{t_num} Z={z_val:.4f} ***")
            self.command.mode(linuxcnc.MODE_MDI)
            self.command.wait_complete()
            self.command.mdi(f"G10 L1 P{t_num} Z{z_val:.4f}")
            self.command.wait_complete()
            self.command.mode(linuxcnc.MODE_MANUAL)
            self.command.load_tool_table()
            self._update_tool_status_bar()
            print(f"✓ Z offset updated: T{t_num} Z={z_val:.4f}")
            print("="*35 + "\n")
        except Exception as e:
            print(f"Update Z offset error: {e}")

    def tool_load(self):
        """
        Load selected tool into spindle via T{n} M6 with G43 (apply offsets).
        G43 activates the tool length compensation immediately after load.
        """
        t_num = self._get_selected_tool_num()
        if t_num is None:
            QMessageBox.warning(self.w, "No Tool Selected", "Select a tool row first.")
            return
        if not STATUS.machine_is_on():
            QMessageBox.warning(self.w, "Machine Off", "Turn machine power ON first.")
            return
        try:
            print(f"\n*** TOOL LOAD: T{t_num} M6 G43 ***")
            self.command.mode(linuxcnc.MODE_MDI)
            self.command.wait_complete()
            self.command.mdi(f"T{t_num} M6")
            self.command.wait_complete()
            self.command.mdi(f"G43 H{t_num}")
            self.command.wait_complete()
            self.command.mode(linuxcnc.MODE_MANUAL)
            self._update_tool_status_bar()
            print(f"✓ Tool T{t_num} loaded with G43 offset compensation")
            print("="*35 + "\n")
        except Exception as e:
            print(f"Tool load error: {e}")

    def tool_unload(self):
        """
        Unload current tool: T0 M6 G49 (cancel TLC + return to no tool).
        """
        if not STATUS.machine_is_on():
            QMessageBox.warning(self.w, "Machine Off", "Turn machine power ON first.")
            return
        try:
            self.stat.poll()
            current_tool = self.stat.tool_in_spindle
        except:
            current_tool = 0
        reply = QMessageBox.question(
            self.w,
            "Unload Tool",
            f"Unload T{current_tool} from spindle?\n(T0 M6 G49)",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        try:
            print(f"\n*** TOOL UNLOAD: T0 M6 G49 ***")
            self.command.mode(linuxcnc.MODE_MDI)
            self.command.wait_complete()
            self.command.mdi("T0 M6")
            self.command.wait_complete()
            self.command.mdi("G49")
            self.command.wait_complete()
            self.command.mode(linuxcnc.MODE_MANUAL)
            self._update_tool_status_bar()
            print("✓ Tool unloaded (T0 M6 G49)")
            print("="*35 + "\n")
        except Exception as e:
            print(f"Tool unload error: {e}")

    # ═══════════════════════════════════════════════════════════════════════
    # — ADDED: AUTO MODE TOOL CHANGE HANDLER —
    # ═══════════════════════════════════════════════════════════════════════

    def _on_tool_in_spindle_changed(self, obj, tool_num):
        """
        Slot called by STATUS whenever tool_in_spindle changes.
        Fires in MANUAL, MDI, and AUTO mode — including M6 during program execution.
        Refreshes table_tools so offsets and active-tool row stay correct.
        If the panel is closed, we still mark a reload-needed flag so the
        table is fresh the next time the user opens it.
        """
        try:
            if self.tool_panel_visible:
                self.tool_reload_table()
            # _update_tool_info_panel() handles the info-bar labels separately
            # via its own change-detection on _last_tool_in_spindle.
            print(f"[AUTO Tool Change] tool_in_spindle → T{tool_num}")
        except Exception as e:
            print(f"Tool change refresh error: {e}")

    # ═══════════════════════════════════════════════════════════════════════
    # — END ADDED: AUTO MODE TOOL CHANGE HANDLER —
    # ═══════════════════════════════════════════════════════════════════════

    # ═══════════════════════════════════════════════════════════════════════
    # — ADDED: TOOL INFORMATION PANEL (beside TOOL MGT button) —
    # ═══════════════════════════════════════════════════════════════════════

    def _update_tool_info_panel(self):
        """
        Update the Tool Information bar (toolInfoContainer).
        Called from periodic_update() every 100 ms — no extra timer needed.

        Change-detection strategy:
          • Tool number change  → re-read stat.tool_table + tool file (full refresh)
          • Spindle speed change → recalculate Vc only (no file I/O)
          • Task mode change     → update AUTO indicator on heading label
          • No change            → skip all work (zero CPU overhead)

        AUTO mode behaviour:
          • toolInfoHeading shows "▌ Tool Information  [ AUTO - LIVE ]" in green
          • Every T-word executed by the program triggers tool_num change → instant refresh
          • Works because stat.tool_in_spindle updates the moment LinuxCNC
            processes a T+M6 block during program execution
        """
        try:
            # ── stat already polled by periodic_update caller ────────────
            tool_num     = self.stat.tool_in_spindle
            task_mode    = self.stat.task_mode

            try:
                spindle_speed = abs(self.stat.spindle[0]['speed'])
            except Exception:
                spindle_speed = 0.0

            # ── 1. AUTO MODE INDICATOR — update heading when mode changes ─
            if task_mode != self._last_task_mode:
                self._last_task_mode = task_mode
                try:
                    if task_mode == linuxcnc.MODE_AUTO:
                        self.w.toolInfoHeading.setText("▌ Tool Information  [ AUTO - LIVE ]")
                        self.w.toolInfoHeading.setStyleSheet(
                            "color: #00e676; font-weight: bold; font-size: 8pt;"
                            "background: transparent; border: none;"
                        )
                    else:
                        self.w.toolInfoHeading.setText("▌ Tool Information")
                        self.w.toolInfoHeading.setStyleSheet(
                            "color: #00aaff; font-weight: bold; font-size: 8pt;"
                            "background: transparent; border: none;"
                        )
                except Exception:
                    pass

            # ── 2. TOOL CHANGE — only re-read when tool_in_spindle changes ─
            tool_changed = (tool_num != self._last_tool_in_spindle)

            if tool_changed:
                self._last_tool_in_spindle = tool_num

                # Defaults for no-tool state
                d_val = 0.0
                z_val = 0.0
                t_str = str(tool_num) if tool_num != 0 else "—"
                d_str = "—"
                z_str = "—"
                desc  = "No tool description available"

                # ── Offsets from stat.tool_table (live, authoritative) ──
                if tool_num != 0:
                    try:
                        for t in self.stat.tool_table:
                            if t.id == tool_num:
                                d_val = t.diameter
                                z_val = t.zoffset
                                d_str = f"{d_val:.3f} mm"
                                z_str = f"{z_val:.3f} mm"
                                break
                    except Exception:
                        pass

                # ── Comment from tool file (only on tool change) ────────
                if tool_num != 0 and self.tool_file_path and os.path.isfile(self.tool_file_path):
                    try:
                        with open(self.tool_file_path, 'r') as fh:
                            for line in fh:
                                raw = line.strip()
                                comment = ""
                                if ';' in raw:
                                    raw, comment = raw.split(';', 1)
                                    comment = comment.strip()
                                tokens = raw.upper().split()
                                t_val = 0
                                for tok in tokens:
                                    if tok.startswith('T') and len(tok) > 1:
                                        try:
                                            t_val = int(tok[1:])
                                        except ValueError:
                                            pass
                                        break
                                if t_val == tool_num:
                                    if comment:
                                        desc = comment
                                    break
                    except Exception:
                        pass

                # ── Cache for Vc recalculation on spindle speed change ──
                self._tool_info_cache = {
                    'd_val': d_val,
                    't_str': t_str,
                    'd_str': d_str,
                    'z_str': z_str,
                    'desc':  desc,
                }

                # ── Push static fields ───────────────────────────────────
                self.w.toolNoValue.setText(t_str)
                self.w.toolDiameterValue.setText(d_str)
                self.w.toolOffsetZValue.setText(z_str)
                self.w.toolDescValue.setText(desc)

                # Log tool change in AUTO mode so it's visible in terminal
                if task_mode == linuxcnc.MODE_AUTO:
                    print(f"[Tool Info] AUTO tool change detected → T{tool_num}"
                          f"  D={d_str}  Z={z_str}  [{desc}]")

                # Reset spindle cache to force Vc recalculation below
                self._last_spindle_speed = -1.0

            # ── 3. Vc — recalculate when spindle speed changes ────────────
            # Round to 1 RPM to avoid float noise triggering constant updates
            spindle_rounded = round(spindle_speed, 0)
            if spindle_rounded != self._last_spindle_speed or tool_changed:
                self._last_spindle_speed = spindle_rounded

                d_val  = self._tool_info_cache.get('d_val', 0.0)
                vc_str = "— m/min"

                if spindle_speed > 0 and d_val > 0:
                    vc = math.pi * d_val * spindle_speed / 1000.0
                    vc_str = f"{vc:.1f} m/min"

                self.w.toolVcValue.setText(vc_str)

        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════════════
    # — END ADDED: TOOL MANAGEMENT —
    # ═══════════════════════════════════════════════════════════════════════

    # ═══════════════════════════════════════════════════════════════════════
    # — ADDED: PREVIEW / OFFSET PAGE TABS (PART 3) —
    # ═══════════════════════════════════════════════════════════════════════

    def setup_graphics_tabs(self):
        """
        Wire the Preview / Offset Page tab buttons.
        Preview  → show gcode_viewer, hide table_offsets
        Offset Page → hide gcode_viewer, show table_offsets + populate it
        Uses QButtonGroup for mutual exclusion.
        """
        try:
            self._graphics_tab_group = QButtonGroup()
            self._graphics_tab_group.addButton(self.w.btn_tab_preview)
            self._graphics_tab_group.addButton(self.w.btn_tab_offsets)
            self._graphics_tab_group.setExclusive(True)
            self.w.btn_tab_preview.clicked.connect(self._show_preview_tab)
            self.w.btn_tab_offsets.clicked.connect(self._show_offsets_tab)
            # Setup offset table columns
            tbl = self.w.table_offsets
            tbl.setColumnCount(4)
            tbl.setHorizontalHeaderLabels(["System", "X", "Y", "Z"])
            tbl.horizontalHeader().setStretchLastSection(True)
            tbl.verticalHeader().hide()
            tbl.verticalHeader().setDefaultSectionSize(22)
            print("✓ Preview/Offset Page tabs connected")
        except Exception as e:
            print(f"Graphics tabs setup note: {e}")

    def _show_preview_tab(self):
        """Switch to Preview: show GCode graphics, hide offset table."""
        try:
            self.w.gcode_viewer.setVisible(True)
            self.w.table_offsets.setVisible(False)
            self.w.btn_tab_preview.setChecked(True)
            self.w.btn_tab_offsets.setChecked(False)
            # Restore size policy so gcode_viewer expands
            from PyQt5.QtWidgets import QSizePolicy
            self.w.gcode_viewer.setSizePolicy(
                QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.w.gcode_viewer.updateGeometry()
        except Exception as e:
            print(f"Preview tab note: {e}")

    def _show_offsets_tab(self):
        """Switch to Offset Page: hide GCode graphics, show + populate offset table."""
        try:
            self.w.gcode_viewer.setVisible(False)
            self.w.table_offsets.setVisible(True)
            self.w.btn_tab_preview.setChecked(False)
            self.w.btn_tab_offsets.setChecked(True)
            # Restore size policy so table_offsets expands
            from PyQt5.QtWidgets import QSizePolicy
            self.w.table_offsets.setSizePolicy(
                QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.w.table_offsets.updateGeometry()
            self._populate_offset_table()
        except Exception as e:
            print(f"Offsets tab note: {e}")

    def _populate_offset_table(self):
        """
        Read work coordinate offsets from stat.g5x_offsets + stat.g92_offset
        and fill table_offsets.
        g5x_offsets is a list of 9 coordinate systems: index 0=G54, 1=G55...8=G59.3
        Each entry is a tuple of (X, Y, Z, A, B, C, U, V, W).
        """
        try:
            self.stat.poll()
            tbl = self.w.table_offsets
            tbl.blockSignals(True)
            tbl.setRowCount(0)

            coord_names = ['G54', 'G55', 'G56', 'G57', 'G58', 'G59',
                           'G59.1', 'G59.2', 'G59.3']
            # Current active system index (0-based)
            active_idx = getattr(self.stat, 'g5x_index', 0)
            if active_idx > 0:
                active_idx -= 1  # stat uses 1-based for g5x_index

            offsets = getattr(self.stat, 'g5x_offsets', [])
            for i, name in enumerate(coord_names):
                if i < len(offsets):
                    off = offsets[i]
                else:
                    off = (0.0, 0.0, 0.0)
                row = tbl.rowCount()
                tbl.insertRow(row)
                # Mark active coord system
                display_name = f"► {name}" if i == active_idx else name
                from PyQt5.QtWidgets import QTableWidgetItem
                from PyQt5.QtGui import QColor
                items = [
                    QTableWidgetItem(display_name),
                    QTableWidgetItem(f"{off[0]:.4f}"),
                    QTableWidgetItem(f"{off[1]:.4f}"),
                    QTableWidgetItem(f"{off[2]:.4f}"),
                ]
                for col, item in enumerate(items):
                    if i == active_idx:
                        item.setForeground(QColor('#00e676'))
                    tbl.setItem(row, col, item)

            # Add G92 row
            g92 = getattr(self.stat, 'g92_offset', (0.0, 0.0, 0.0))
            row = tbl.rowCount()
            tbl.insertRow(row)
            from PyQt5.QtWidgets import QTableWidgetItem
            from PyQt5.QtGui import QColor
            for col, val in enumerate(['G92',
                                       f"{g92[0]:.4f}",
                                       f"{g92[1]:.4f}",
                                       f"{g92[2]:.4f}"]):
                item = QTableWidgetItem(val)
                item.setForeground(QColor('#f39c12'))
                tbl.setItem(row, col, item)

            tbl.blockSignals(False)
        except Exception as e:
            print(f"Offset table populate error: {e}")
            try:
                self.w.table_offsets.blockSignals(False)
            except Exception:
                pass

    # ═══════════════════════════════════════════════════════════════════════
    # — END ADDED: PREVIEW / OFFSET PAGE TABS —
    # ═══════════════════════════════════════════════════════════════════════

    # ═══════════════════════════════════════════════════════════════════════
    # — ADDED: TOUCH-OFF SECTION (PART 2) —
    # ═══════════════════════════════════════════════════════════════════════

    def setup_touchoff_section(self):
        """
        Wire the TOUCH OFF button and all axis buttons.
        frame_touchoff_buttons is hidden until btn_touch_off is toggled.
        """
        try:
            self.w.btn_touch_off.clicked.connect(self._toggle_touchoff_buttons)
            self.w.btn_to_x.clicked.connect(lambda: self._touchoff_axis_keypad('X'))
            self.w.btn_to_y.clicked.connect(lambda: self._touchoff_axis_keypad('Y'))
            self.w.btn_to_z.clicked.connect(lambda: self._touchoff_axis_keypad('Z'))
            self.w.btn_to_g92.clicked.connect(self._touchoff_g92)
            self.w.btn_to_set_selected.clicked.connect(self._touchoff_set_selected)
            print("✓ Touch-off section connected")

            # FIX 2 — Hide touch off button by default; show only in MANUAL mode
            try:
                self.w.btn_touch_off.setVisible(False)
            except Exception:
                pass

            # FIX 3 — Hide Preview / Offset tab buttons by default
            try:
                self.w.btn_tab_preview.setVisible(False)
                self.w.btn_tab_offsets.setVisible(False)
            except Exception:
                pass

            # FIX 2 — Connect STATUS mode signals to show/hide touch off button
            STATUS.connect('mode-manual', self._on_mode_manual_touchoff)
            STATUS.connect('mode-mdi',    self._on_mode_mdi_touchoff)
            STATUS.connect('mode-auto',   self._on_mode_auto_touchoff)

        except Exception as e:
            print(f"Touch-off setup note: {e}")

    def _toggle_touchoff_buttons(self):
        """Show/hide the axis button row and Preview/Offset buttons when TOUCH OFF is toggled."""
        try:
            visible = self.w.btn_touch_off.isChecked()
            self.w.frame_touchoff_buttons.setVisible(visible)
            # FIX 3 — show/hide Preview and Offset tab buttons with Touch Off
            self.w.btn_tab_preview.setVisible(visible)
            self.w.btn_tab_offsets.setVisible(visible)
        except Exception as e:
            print(f"Touch-off toggle note: {e}")

    # ── FIX 2: Touch Off button mode visibility ──────────────────────────
    def _on_mode_manual_touchoff(self, *args):
        """Show Touch Off button when machine enters MANUAL mode."""
        try:
            self.w.btn_touch_off.setVisible(True)
        except Exception as e:
            print(f"show touch off note: {e}")

    def _on_mode_mdi_touchoff(self, *args):
        """Hide Touch Off button (and its sub-buttons) when entering MDI."""
        try:
            self.w.btn_touch_off.setChecked(False)
            self.w.frame_touchoff_buttons.setVisible(False)
            self.w.btn_touch_off.setVisible(False)
            # FIX 3 — also hide Preview/Offset buttons
            self.w.btn_tab_preview.setVisible(False)
            self.w.btn_tab_offsets.setVisible(False)
        except Exception as e:
            print(f"hide touch off (MDI) note: {e}")

    def _on_mode_auto_touchoff(self, *args):
        """Hide Touch Off button (and its sub-buttons) when entering AUTO."""
        try:
            self.w.btn_touch_off.setChecked(False)
            self.w.frame_touchoff_buttons.setVisible(False)
            self.w.btn_touch_off.setVisible(False)
            # FIX 3 — also hide Preview/Offset buttons
            self.w.btn_tab_preview.setVisible(False)
            self.w.btn_tab_offsets.setVisible(False)
        except Exception as e:
            print(f"hide touch off (AUTO) note: {e}")
    # ── END FIX 2/3 ───────────────────────────────────────────────────────

    def _touchoff_axis_keypad(self, axis):
        """
        Open a numeric keypad dialog for the given axis.
        On OK: apply the entered value as a work offset on the active G5x system.
        Uses ACTION.SET_AXIS_ORIGIN which issues the correct G10 L20 command
        against the currently active coordinate system — never hardcodes G54.
        """
        axis_upper = axis.upper()
        self._touchoff_axis = axis_upper

        # Map axis letter to position index for current position display
        axis_idx = {'X': 0, 'Y': 1, 'Z': 2}.get(axis_upper, 0)

        # Get current relative position for this axis
        try:
            self.stat.poll()
            pos = self.stat.position
            g5x = getattr(self.stat, 'g5x_offset', (0,) * 9)
            g92 = getattr(self.stat, 'g92_offset', (0,) * 9)
            tool_off = getattr(self.stat, 'tool_offset', (0,) * 9)
            current_val = (pos[axis_idx]
                           - g5x[axis_idx]
                           - g92[axis_idx]
                           - tool_off[axis_idx])
        except Exception:
            current_val = 0.0

        # Build simple numeric input dialog (Gmoccapy-style)
        value, ok = self._numeric_keypad_dialog(
            title=f"Set axis {axis_upper} to:",
            current_value=current_val
        )
        if not ok:
            return

        # Capture values for the deferred callback closure
        _axis = axis_upper
        _value = value

        def _apply_touchoff():
            """
            Runs on the main thread after the dialog has closed.
            Uses the exact same sequence as execute_mdi() which is proven
            to work — same linuxcnc.command() object, same blocking pattern,
            same main-thread context.  QTimer.singleShot(0) defers execution
            until Qt has finished closing the dialog, preventing any
            event-loop re-entrancy issues.
            """
            try:
                if not STATUS.machine_is_on():
                    print("Touch off skipped: machine is OFF")
                    return

                self.stat.poll()
                g5x_index = getattr(self.stat, 'g5x_index', 1)
                p_num = max(1, g5x_index)
                gcode = f"G10 L20 P{p_num} {_axis}{_value:.4f}"
                print(f"→ Touch off applying: {gcode}")

                # ── Step 1: Abort if interpreter busy ─────────────────────
                self.stat.poll()
                if self.stat.interp_state != linuxcnc.INTERP_IDLE:
                    self.command.abort()
                    deadline = time.time() + 2.0
                    while time.time() < deadline:
                        self.stat.poll()
                        if self.stat.interp_state == linuxcnc.INTERP_IDLE:
                            break
                        time.sleep(0.02)

                # ── Step 2: Switch to MDI ─────────────────────────────────
                self.command.mode(linuxcnc.MODE_MDI)
                rc = self.command.wait_complete(3.0)
                if rc == linuxcnc.RCS_ERROR:
                    print("✗ Touch off: mode switch RCS_ERROR")
                    return

                # ── Step 3: Confirm MDI mode ──────────────────────────────
                deadline = time.time() + 0.5
                while time.time() < deadline:
                    self.stat.poll()
                    if self.stat.task_mode == linuxcnc.MODE_MDI:
                        break
                    time.sleep(0.02)
                if self.stat.task_mode != linuxcnc.MODE_MDI:
                    print("✗ Touch off: failed to enter MDI mode")
                    return

                # ── Step 4: Confirm interpreter idle ─────────────────────
                deadline = time.time() + 1.0
                while time.time() < deadline:
                    self.stat.poll()
                    if self.stat.interp_state == linuxcnc.INTERP_IDLE:
                        break
                    time.sleep(0.02)

                # ── Step 5: Drain stale errors ────────────────────────────
                try:
                    _ec = linuxcnc.error_channel()
                    while _ec.poll():
                        pass
                except Exception:
                    pass

                # ── Step 6: Send G10 L20 ─────────────────────────────────
                self.command.mdi(gcode)
                self.command.wait_complete(10.0)
                self.stat.poll()

                # ── Step 7: Return to MANUAL ──────────────────────────────
                self.command.mode(linuxcnc.MODE_MANUAL)
                self.command.wait_complete(2.0)
                self.stat.poll()

                print(f"✓ Touch off {_axis} → {_value:.4f} (G10 L20 P{p_num})")

                # ── Step 8: Force full display refresh ────────────────────
                try:
                    STATUS.emit('reload-display')
                except Exception:
                    pass
                try:
                    STATUS.emit('update-machine-log')
                except Exception:
                    pass
                try:
                    if hasattr(self.w, 'gcode_viewer') and self.w.gcode_viewer.isVisible():
                        self.w.gcode_viewer.updateGL()
                except Exception:
                    pass
                try:
                    if self.w.table_offsets.isVisible():
                        self._populate_offset_table()
                except Exception:
                    pass

            except Exception as e:
                print(f"✗ Touch off apply error: {e}")

        # Defer by 0 ms — lets Qt close the dialog before executing
        QTimer.singleShot(0, _apply_touchoff)

    def _touchoff_g92(self):
        """
        Apply G92 offset to the last selected axis.
        Prompts for value; issues G92 Xvalue (or Y/Z etc.).
        If no axis was selected yet, uses X as default.
        """
        axis = self._touchoff_axis if self._touchoff_axis else 'X'
        axis_idx = {'X': 0, 'Y': 1, 'Z': 2}.get(axis, 0)

        try:
            self.stat.poll()
            pos = self.stat.position
            g5x = getattr(self.stat, 'g5x_offset', (0,) * 9)
            current_val = pos[axis_idx] - g5x[axis_idx]
        except Exception:
            current_val = 0.0

        value, ok = self._numeric_keypad_dialog(
            title=f"G92 — Set axis {axis} to:",
            current_value=current_val
        )
        if not ok:
            return

        try:
            gcode = f"G92 {axis}{value:.4f}"
            self._send_mdi_command(gcode)
            print(f"✓ G92 {axis} → {value:.4f}")
            if self.w.table_offsets.isVisible():
                self._populate_offset_table()
        except Exception as e:
            print(f"G92 apply error: {e}")

    def _touchoff_set_selected(self):
        """
        Apply value to currently active coordinate system for the last selected axis.
        Reads the active G5x index from stat (never hardcodes G54).
        Uses G10 L2 Pn to set the absolute offset value.
        """
        axis = self._touchoff_axis if self._touchoff_axis else 'X'
        axis_idx = {'X': 0, 'Y': 1, 'Z': 2}.get(axis, 0)

        try:
            self.stat.poll()
            # g5x_index: 0=G53 machine, 1=G54, 2=G55...
            g5x_index = getattr(self.stat, 'g5x_index', 1)
            p_num = max(1, g5x_index)   # P number for G10 L2
            pos = self.stat.position
            current_val = pos[axis_idx]
        except Exception:
            current_val = 0.0
            p_num = 1

        value, ok = self._numeric_keypad_dialog(
            title=f"Set {axis} offset in active coord system (G10 L2 P{p_num}):",
            current_value=current_val
        )
        if not ok:
            return

        try:
            gcode = f"G10 L2 P{p_num} {axis}{value:.4f}"
            self._send_mdi_command(gcode)
            print(f"✓ SET SELECTED {axis} → {value:.4f}  (G10 L2 P{p_num})")
            if self.w.table_offsets.isVisible():
                self._populate_offset_table()
        except Exception as e:
            print(f"Set selected apply error: {e}")

    def _numeric_keypad_dialog(self, title="Enter value:", current_value=0.0):
        """
        Gmoccapy-style numeric entry dialog.
        Returns (float_value, accepted_bool).
        Uses a custom dialog with digit buttons for touchscreen-friendly input.
        """
        from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
                                     QLabel, QLineEdit, QPushButton, QGridLayout)
        from PyQt5.QtCore import Qt

        dlg = QDialog(self.w)
        dlg.setWindowTitle(title)
        dlg.setModal(True)
        dlg.setMinimumWidth(300)
        dlg.setStyleSheet("""
            QDialog { background-color: #1a1a2e; color: white; }
            QLabel  { color: #00aaff; font-weight: bold; font-size: 10pt; }
            QLineEdit {
                background-color: #0f3460; color: #00ff00;
                border: 2px solid #1c5980; border-radius: 4px;
                font-size: 16pt; font-weight: bold; padding: 4px;
            }
            QPushButton {
                background-color: #2c3e50; color: white;
                border: 1px solid #1c5980; border-radius: 4px;
                font-size: 13pt; font-weight: bold;
                min-width: 52px; min-height: 44px;
            }
            QPushButton:hover  { background-color: #3d5166; }
            QPushButton:pressed { background-color: #1c5980; }
            #btn_ok  { background-color: #27ae60; border-color: #1e8449; }
            #btn_ok:hover { background-color: #2ecc71; }
            #btn_cancel { background-color: #c0392b; border-color: #943126; }
            #btn_cancel:hover { background-color: #e74c3c; }
        """)

        vbox = QVBoxLayout(dlg)
        vbox.setSpacing(6)
        vbox.setContentsMargins(12, 12, 12, 12)

        lbl = QLabel(title)
        lbl.setWordWrap(True)
        vbox.addWidget(lbl)

        edit = QLineEdit(f"{current_value:.4f}")
        edit.setAlignment(Qt.AlignRight)
        edit.selectAll()
        vbox.addWidget(edit)

        grid = QGridLayout()
        grid.setSpacing(4)
        btn_labels = [
            ('7', 0, 0), ('8', 0, 1), ('9', 0, 2),
            ('4', 1, 0), ('5', 1, 1), ('6', 1, 2),
            ('1', 2, 0), ('2', 2, 1), ('3', 2, 2),
            ('0', 3, 0), ('.', 3, 1), ('-', 3, 2),
        ]
        for label, row, col in btn_labels:
            b = QPushButton(label)
            b.clicked.connect(lambda checked, ch=label: edit.insert(ch))
            grid.addWidget(b, row, col)

        btn_bs = QPushButton('⌫')
        btn_bs.clicked.connect(lambda: edit.setText(edit.text()[:-1]))
        grid.addWidget(btn_bs, 4, 0)

        btn_clr = QPushButton('C')
        btn_clr.clicked.connect(lambda: edit.clear())
        grid.addWidget(btn_clr, 4, 1, 1, 2)

        vbox.addLayout(grid)

        hbox = QHBoxLayout()
        btn_ok = QPushButton('OK')
        btn_ok.setObjectName('btn_ok')
        btn_cancel = QPushButton('Cancel')
        btn_cancel.setObjectName('btn_cancel')
        btn_ok.clicked.connect(dlg.accept)
        btn_cancel.clicked.connect(dlg.reject)
        hbox.addWidget(btn_ok)
        hbox.addWidget(btn_cancel)
        vbox.addLayout(hbox)

        result = dlg.exec_()
        if result == QDialog.Accepted:
            try:
                val = float(edit.text())
                return val, True
            except ValueError:
                return 0.0, False
        return 0.0, False

    def _send_mdi_command(self, gcode_command, on_complete=None):
        """
        Send a single MDI command off the Qt main thread using QThread so the
        event loop is never blocked (blocking wait_complete on the main thread
        deadlocks LinuxCNC's task loop, causing the silent no-op bug).

        on_complete: optional callable — invoked on the main thread after the
        command finishes (use this for DRO / offset-table refresh).
        """
        from PyQt5.QtCore import QThread, pyqtSignal, QObject
        import linuxcnc as _lc
        import time as _t

        class _MdiWorker(QThread):
            finished = pyqtSignal(bool, str)   # (success, error_msg)

            def __init__(self, cmd):
                super().__init__()
                self._cmd = cmd

            def run(self):
                try:
                    _cmd_obj = linuxcnc.command()
                    _stat_obj = linuxcnc.stat()

                    # Wait for interpreter idle (max 3 s)
                    deadline = _t.time() + 3.0
                    while _t.time() < deadline:
                        _stat_obj.poll()
                        if _stat_obj.interp_state == _lc.INTERP_IDLE:
                            break
                        _t.sleep(0.02)

                    _cmd_obj.mode(_lc.MODE_MDI)
                    _cmd_obj.wait_complete(3.0)

                    # Wait for MODE_MDI to be confirmed (max 1 s)
                    deadline = _t.time() + 1.0
                    while _t.time() < deadline:
                        _stat_obj.poll()
                        if _stat_obj.task_mode == _lc.MODE_MDI:
                            break
                        _t.sleep(0.02)

                    _cmd_obj.mdi(self._cmd)
                    _cmd_obj.wait_complete(10.0)
                    _stat_obj.poll()

                    _cmd_obj.mode(_lc.MODE_MANUAL)
                    _cmd_obj.wait_complete(2.0)

                    self.finished.emit(True, '')
                except Exception as exc:
                    self.finished.emit(False, str(exc))

        worker = _MdiWorker(gcode_command)

        def _on_done(success, err):
            if success:
                print(f"✓ MDI done: {gcode_command}")
            else:
                print(f"✗ MDI error ({gcode_command}): {err}")
            # Always refresh display on completion
            try:
                self.stat.poll()
            except Exception:
                pass
            try:
                STATUS.emit('reload-display')
            except Exception:
                pass
            try:
                STATUS.emit('update-machine-log')
            except Exception:
                pass
            try:
                if hasattr(self.w, 'gcode_viewer') and self.w.gcode_viewer.isVisible():
                    self.w.gcode_viewer.updateGL()
            except Exception:
                pass
            try:
                if self.w.table_offsets.isVisible():
                    self._populate_offset_table()
            except Exception:
                pass
            if callable(on_complete):
                try:
                    on_complete()
                except Exception:
                    pass
            # Keep reference alive until thread finishes
            try:
                self._mdi_workers.discard(worker)
            except Exception:
                pass

        worker.finished.connect(_on_done)

        # Keep a reference so the thread isn't garbage-collected mid-run
        if not hasattr(self, '_mdi_workers'):
            self._mdi_workers = set()
        self._mdi_workers.add(worker)

        worker.start()

    # ═══════════════════════════════════════════════════════════════════════
    # — END ADDED: TOUCH-OFF SECTION —
    # ═══════════════════════════════════════════════════════════════════════

def get_handlers(halcomp, widgets, paths):
    """Return handler"""
    return [HandlerClass(halcomp, widgets, paths)]
