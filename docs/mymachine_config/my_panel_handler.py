#!/usr/bin/env python3
"""
QtVCP Panel Handler - Mode-Based Visibility Control
Version: 6.1 - ADDED INDIVIDUAL AXIS HOMING + DRO OVERLAY
"""

from PyQt5.QtCore import Qt, QTimer, QObject, QEvent
from PyQt5.QtWidgets import QButtonGroup, QFileDialog, QShortcut, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton
from PyQt5.QtGui import QTextCursor, QTextCharFormat, QColor, QKeySequence
from qtvcp.core import Status, Action, Info
import linuxcnc
import os
import time

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
        
    def initialized__(self):
        """Called after widgets are initialized"""
        print("="*50)
        print("QtVCP Panel - Mode-Based Visibility Control")
        print("Version 6.1 - INDIVIDUAL AXIS HOMING + DRO OVERLAY")
        print("="*50)
        
        # Configure DRO
        self.setup_dro()
        
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
        self.w.btn_home_all.clicked.connect(self.home_all)
        
        # — ADDED: JOINT SELECT BUTTON —
        # Connect joint assignment dialog button
        self.w.btn_joint_select.clicked.connect(self.open_joint_assignment_dialog)
        # — END ADDED: JOINT SELECT BUTTON —
        
        # — ADDED FOR AXIS HOMING BUTTONS —
        # Connect individual axis homing buttons
        self.w.btn_home_x.clicked.connect(self.home_x_axis)
        self.w.btn_home_y.clicked.connect(self.home_y_axis)
        self.w.btn_home_z.clicked.connect(self.home_z_axis)
        # — END ADDED FOR AXIS HOMING BUTTONS —
        
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
        
        # Setup periodic status update timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.periodic_update)
        self.timer.start(100)  # 100ms update rate
        
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
        except:
            pass
    
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
        """Execute MDI command"""
        if not STATUS.machine_is_on():
            print("ERROR: Power is OFF!")
            print("Click POWER ON first")
            return
        
        # Check if homed
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
        
        print("\n" + "="*50)
        print(f"EXECUTING MDI: {gcode_command}")
        print("="*50)
        
        try:
            # Ensure we're in MDI mode
            self.command.mode(linuxcnc.MODE_MDI)
            self.command.wait_complete(1.0)
            
            # Poll to confirm mode
            self.stat.poll()
            if self.stat.task_mode != linuxcnc.MODE_MDI:
                print("✗ ERROR: Failed to enter MDI mode!")
                print(f"Current mode: {self.stat.task_mode}")
                print("="*50 + "\n")
                return
            
            # Execute command
            self.command.mdi(gcode_command)
            
            # Wait for interpreter to start
            time.sleep(0.1)
            
            # Check for immediate errors
            self.stat.poll()
            if self.stat.interp_state == linuxcnc.INTERP_IDLE:
                error = self.command.error()
                if error and error[0]:
                    print(f"✗ LinuxCNC ERROR: {error}")
                    print("Common causes:")
                    print("  - Axes not homed")
                    print("  - Command exceeds soft limits")
                    print("  - Invalid G-code syntax")
                    print("="*50 + "\n")
                    return
            
            # Add to history
            current = self.w.text_mdi_history.toPlainText()
            if current:
                self.w.text_mdi_history.setPlainText(current + "\n" + gcode_command)
            else:
                self.w.text_mdi_history.setPlainText(gcode_command)
            
            # Scroll to bottom
            scrollbar = self.w.text_mdi_history.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
            
            # Clear input
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
    
    def update_feedrate_override(self, value):
        """Feed rate override"""
        self.w.label_feedrate.setText(f"{value}%")
        ACTION.SET_FEED_RATE(value / 100.0)
    
    def update_rapid_override(self, value):
        """Rapid override"""
        self.w.label_rapidrate.setText(f"{value}%")
        ACTION.SET_RAPID_RATE(value / 100.0)

def get_handlers(halcomp, widgets, paths):
    """Return handler"""
    return [HandlerClass(halcomp, widgets, paths)]
