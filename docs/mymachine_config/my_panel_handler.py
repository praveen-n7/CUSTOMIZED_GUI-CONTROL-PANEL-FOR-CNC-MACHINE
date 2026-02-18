#!/usr/bin/env python3
"""
QtVCP Panel Handler - Mode-Based Visibility Control
Version: 7.0 - FULLY INI-DRIVEN MACHINE CONFIGURATION
All machine-specific parameters now loaded from active INI file
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
        
        # Machine configuration - loaded from INI
        self.machine_config = {}
        
        # Jog settings - will be populated from INI
        self.jog_speed = 500  # Temporary default, overridden by load_machine_configuration
        self.jog_increment = 10.0  # Temporary default
        self.jog_mode = "increment"
        self.jog_increments = []  # Will be populated based on units
        
        # Spindle settings - will be populated from INI
        self.spindle_speed = 1000  # Temporary default
        
        # Current mode
        self.current_mode = "MANUAL"
        
        # Auto mode settings
        self.loaded_program_path = None
        self.loaded_program_lines = []
        self.auto_feedrate_override = 100
        self.last_highlighted_line = -1
        
        # Joint to axis mapping - will be populated from INI
        self.home_x_joint = 0  # Temporary default
        self.home_y_joint = 1  # Temporary default
        self.home_z_joint = 2  # Temporary default
        self.axis_to_joint_map = {}  # Maps 'X' -> joint_num, 'Y' -> joint_num, etc.
        
        # Axis velocity tracking
        self.max_velocity = 0.0
        self.is_metric = True  # Will be determined from INI
        
        # Load all machine configuration from INI file
        self.load_machine_configuration()
        
    def load_machine_configuration(self):
        """
        Load all machine-specific configuration from active INI file.
        This makes the handler completely machine-independent.
        """
        print("\n" + "="*60)
        print("LOADING MACHINE CONFIGURATION FROM INI")
        print("="*60)
        
        try:
            # ═══════════════════════════════════════════════════════════
            # 1. DETECT LINEAR UNITS (metric vs imperial)
            # ═══════════════════════════════════════════════════════════
            try:
                # Read from INFO object (preferred method)
                linear_units = INFO.LINEAR_UNITS
                if linear_units:
                    if 'mm' in linear_units.lower():
                        self.is_metric = True
                        self.machine_config['units'] = 'metric'
                        self.machine_config['units_label'] = 'mm'
                    elif 'inch' in linear_units.lower() or 'in' in linear_units.lower():
                        self.is_metric = False
                        self.machine_config['units'] = 'imperial'
                        self.machine_config['units_label'] = 'in'
                    else:
                        # Fallback to INI file parsing
                        ini = linuxcnc.ini(INFO.INI_FILE)
                        traj_units = ini.find('TRAJ', 'LINEAR_UNITS')
                        if traj_units and 'mm' in traj_units.lower():
                            self.is_metric = True
                            self.machine_config['units'] = 'metric'
                            self.machine_config['units_label'] = 'mm'
                        else:
                            self.is_metric = False
                            self.machine_config['units'] = 'imperial'
                            self.machine_config['units_label'] = 'in'
                else:
                    # Default fallback
                    self.is_metric = True
                    self.machine_config['units'] = 'metric'
                    self.machine_config['units_label'] = 'mm'
            except Exception as e:
                print(f"  ⚠ Units detection error: {e}, defaulting to metric")
                self.is_metric = True
                self.machine_config['units'] = 'metric'
                self.machine_config['units_label'] = 'mm'
            
            print(f"✓ Linear Units: {self.machine_config['units']} ({self.machine_config['units_label']})")
            
            # ═══════════════════════════════════════════════════════════
            # 2. DETECT JOINT COUNT
            # ═══════════════════════════════════════════════════════════
            try:
                joint_count = INFO.JOINT_COUNT
                self.machine_config['joint_count'] = joint_count
            except Exception as e:
                print(f"  ⚠ Joint count error: {e}, defaulting to 3")
                self.machine_config['joint_count'] = 3
            
            print(f"✓ Joint Count: {self.machine_config['joint_count']}")
            
            # ═══════════════════════════════════════════════════════════
            # 3. DETECT AXIS LETTERS FROM COORDINATES
            # ═══════════════════════════════════════════════════════════
            try:
                # Read COORDINATES from [TRAJ] section
                coordinates = INFO.COORDINATES
                if coordinates:
                    # Parse coordinates string (e.g., "XYZ", "XYZA", "XYZAB")
                    self.machine_config['axes'] = list(coordinates.upper())
                else:
                    # Fallback: try reading directly from INI
                    ini = linuxcnc.ini(INFO.INI_FILE)
                    coords = ini.find('TRAJ', 'COORDINATES')
                    if coords:
                        self.machine_config['axes'] = list(coords.upper())
                    else:
                        # Ultimate fallback
                        self.machine_config['axes'] = ['X', 'Y', 'Z']
            except Exception as e:
                print(f"  ⚠ Axis detection error: {e}, defaulting to XYZ")
                self.machine_config['axes'] = ['X', 'Y', 'Z']
            
            print(f"✓ Axes: {' '.join(self.machine_config['axes'])}")
            
            # ═══════════════════════════════════════════════════════════
            # 4. BUILD AXIS-TO-JOINT MAPPING
            # ═══════════════════════════════════════════════════════════
            # Assume trivial kinematics: axis index = joint index
            for idx, axis_letter in enumerate(self.machine_config['axes']):
                if idx < self.machine_config['joint_count']:
                    self.axis_to_joint_map[axis_letter] = idx
            
            print(f"✓ Axis-to-Joint Map: {self.axis_to_joint_map}")
            
            # ═══════════════════════════════════════════════════════════
            # 5. SET DEFAULT HOME JOINT ASSIGNMENTS
            # ═══════════════════════════════════════════════════════════
            # Home buttons are labeled X, Y, Z
            # Map them to corresponding joints based on axis configuration
            self.home_x_joint = self.axis_to_joint_map.get('X', 0)
            self.home_y_joint = self.axis_to_joint_map.get('Y', 1)
            self.home_z_joint = self.axis_to_joint_map.get('Z', 2)
            
            print(f"✓ Home Button Mapping: X→Joint{self.home_x_joint}, Y→Joint{self.home_y_joint}, Z→Joint{self.home_z_joint}")
            
            # ═══════════════════════════════════════════════════════════
            # 6. LOAD JOINT MAX VELOCITIES
            # ═══════════════════════════════════════════════════════════
            try:
                ini = linuxcnc.ini(INFO.INI_FILE)
                joint_velocities = []
                
                for joint_num in range(self.machine_config['joint_count']):
                    try:
                        max_vel = ini.find(f'JOINT_{joint_num}', 'MAX_VELOCITY')
                        if max_vel:
                            joint_velocities.append(float(max_vel))
                        else:
                            joint_velocities.append(25.0)  # Fallback
                    except:
                        joint_velocities.append(25.0)  # Fallback
                
                self.machine_config['joint_max_velocities'] = joint_velocities
                
                # Find global maximum velocity for jog speed limits
                if joint_velocities:
                    self.max_velocity = min(joint_velocities)  # Use minimum to stay safe
                else:
                    self.max_velocity = 25.0
                
            except Exception as e:
                print(f"  ⚠ Velocity detection error: {e}, using defaults")
                self.machine_config['joint_max_velocities'] = [25.0] * self.machine_config['joint_count']
                self.max_velocity = 25.0
            
            print(f"✓ Joint Max Velocities: {self.machine_config['joint_max_velocities']}")
            print(f"✓ Global Max Velocity (for jog): {self.max_velocity} {self.machine_config['units_label']}/s")
            
            # ═══════════════════════════════════════════════════════════
            # 7. SET DEFAULT JOG SPEED (20% of max velocity)
            # ═══════════════════════════════════════════════════════════
            # Convert to mm/min or in/min for display
            self.jog_speed = int(self.max_velocity * 60.0 * 0.20)  # 20% of max, converted to per-minute
            print(f"✓ Default Jog Speed: {self.jog_speed} {self.machine_config['units_label']}/min (20% of max)")
            
            # ═══════════════════════════════════════════════════════════
            # 8. GENERATE JOG INCREMENTS BASED ON UNITS
            # ═══════════════════════════════════════════════════════════
            if self.is_metric:
                # Metric increments: 10mm, 1mm, 0.1mm, 0.01mm
                self.jog_increments = [10.0, 1.0, 0.1, 0.01]
                self.jog_increment = 10.0  # Default
            else:
                # Imperial increments: 1in, 0.1in, 0.01in, 0.001in
                self.jog_increments = [1.0, 0.1, 0.01, 0.001]
                self.jog_increment = 0.1  # Default
            
            self.machine_config['jog_increments'] = self.jog_increments
            print(f"✓ Jog Increments: {self.jog_increments} {self.machine_config['units_label']}")
            
            # ═══════════════════════════════════════════════════════════
            # 9. LOAD SPINDLE CONFIGURATION
            # ═══════════════════════════════════════════════════════════
            try:
                ini = linuxcnc.ini(INFO.INI_FILE)
                
                # Try to read MAX_FORWARD_VELOCITY from [SPINDLE_0]
                max_spindle = ini.find('SPINDLE_0', 'MAX_FORWARD_VELOCITY')
                if max_spindle:
                    self.machine_config['max_spindle_speed'] = float(max_spindle)
                else:
                    # Fallback: try old-style [DISPLAY]
                    max_spindle = ini.find('DISPLAY', 'MAX_SPINDLE_SPEED')
                    if max_spindle:
                        self.machine_config['max_spindle_speed'] = float(max_spindle)
                    else:
                        self.machine_config['max_spindle_speed'] = 24000.0  # Default
                
                # Set default spindle speed to 20% of max
                self.spindle_speed = int(self.machine_config['max_spindle_speed'] * 0.20)
                
            except Exception as e:
                print(f"  ⚠ Spindle detection error: {e}, using defaults")
                self.machine_config['max_spindle_speed'] = 24000.0
                self.spindle_speed = 1000
            
            print(f"✓ Max Spindle Speed: {self.machine_config['max_spindle_speed']} RPM")
            print(f"✓ Default Spindle Speed: {self.spindle_speed} RPM (20% of max)")
            
            # ═══════════════════════════════════════════════════════════
            # 10. LOAD DEFAULT LINEAR VELOCITY FROM [TRAJ]
            # ═══════════════════════════════════════════════════════════
            try:
                ini = linuxcnc.ini(INFO.INI_FILE)
                default_vel = ini.find('TRAJ', 'DEFAULT_LINEAR_VELOCITY')
                if default_vel:
                    self.machine_config['default_linear_velocity'] = float(default_vel)
                else:
                    self.machine_config['default_linear_velocity'] = 5.0
            except:
                self.machine_config['default_linear_velocity'] = 5.0
            
            print(f"✓ Default Linear Velocity: {self.machine_config['default_linear_velocity']} {self.machine_config['units_label']}/s")
            
            print("="*60)
            print("MACHINE CONFIGURATION LOADED SUCCESSFULLY")
            print("="*60 + "\n")
            
        except Exception as e:
            print(f"⚠ CRITICAL ERROR loading machine configuration: {e}")
            print("Using fallback defaults")
            # Set safe fallback values
            self.machine_config = {
                'joint_count': 3,
                'axes': ['X', 'Y', 'Z'],
                'units': 'metric',
                'units_label': 'mm',
                'joint_max_velocities': [25.0, 25.0, 20.0],
                'max_spindle_speed': 24000.0,
                'jog_increments': [10.0, 1.0, 0.1, 0.01],
                'default_linear_velocity': 5.0
            }
            self.is_metric = True
            self.max_velocity = 25.0
            self.jog_speed = 300
            self.spindle_speed = 1000
            self.jog_increments = [10.0, 1.0, 0.1, 0.01]
            self.jog_increment = 10.0
            print("="*60 + "\n")
        
    def initialized__(self):
        """Called after widgets are initialized"""
        print("="*50)
        print("QtVCP Panel - Mode-Based Visibility Control")
        print("Version 7.0 - FULLY INI-DRIVEN CONFIGURATION")
        print("="*50)
        
        # Configure DRO dynamically based on detected axes
        self.setup_dro_dynamic()
        
        # Configure jog controls dynamically
        self.setup_jog_controls_dynamic()
        
        # Configure spindle controls dynamically
        self.setup_spindle_controls_dynamic()
        
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
        
        # Connect joint assignment dialog button
        self.w.btn_joint_select.clicked.connect(self.open_joint_assignment_dialog)
        
        # Connect individual axis homing buttons
        self.w.btn_home_x.clicked.connect(self.home_x_axis)
        self.w.btn_home_y.clicked.connect(self.home_y_axis)
        self.w.btn_home_z.clicked.connect(self.home_z_axis)
        
        # Connect MDI controls
        self.w.btn_mdi_execute.clicked.connect(self.execute_mdi)
        self.w.btn_mdi_clear.clicked.connect(self.clear_mdi)
        self.w.text_mdi_input.returnPressed.connect(self.execute_mdi)
        
        # Connect Auto controls
        self.w.btn_load_program.clicked.connect(self.load_program)
        self.w.btn_cycle_start.clicked.connect(self.cycle_start)
        self.w.btn_pause.clicked.connect(self.pause_program)
        self.w.btn_stop.clicked.connect(self.stop_program)
        
        # Connect jog increment buttons - use dynamic increments
        self.w.btn_jog_continuous.clicked.connect(lambda: self.set_jog_increment("continuous"))
        if len(self.jog_increments) >= 4:
            self.w.btn_jog_10mm.clicked.connect(lambda: self.set_jog_increment(self.jog_increments[0]))
            self.w.btn_jog_1mm.clicked.connect(lambda: self.set_jog_increment(self.jog_increments[1]))
            self.w.btn_jog_0_1mm.clicked.connect(lambda: self.set_jog_increment(self.jog_increments[2]))
            self.w.btn_jog_0_01mm.clicked.connect(lambda: self.set_jog_increment(self.jog_increments[3]))
        
        # Connect jog velocity slider
        self.w.slider_jog_velocity.valueChanged.connect(self.update_jog_velocity)
        
        # Connect jog buttons - use mapped joints
        self.w.btn_jog_xplus.pressed.connect(lambda: self.jog_joint(self.home_x_joint, 1))
        self.w.btn_jog_xplus.released.connect(lambda: self.jog_stop(self.home_x_joint))
        self.w.btn_jog_xminus.pressed.connect(lambda: self.jog_joint(self.home_x_joint, -1))
        self.w.btn_jog_xminus.released.connect(lambda: self.jog_stop(self.home_x_joint))
        
        self.w.btn_jog_yplus.pressed.connect(lambda: self.jog_joint(self.home_y_joint, 1))
        self.w.btn_jog_yplus.released.connect(lambda: self.jog_stop(self.home_y_joint))
        self.w.btn_jog_yminus.pressed.connect(lambda: self.jog_joint(self.home_y_joint, -1))
        self.w.btn_jog_yminus.released.connect(lambda: self.jog_stop(self.home_y_joint))
        
        self.w.btn_jog_zplus.pressed.connect(lambda: self.jog_joint(self.home_z_joint, 1))
        self.w.btn_jog_zplus.released.connect(lambda: self.jog_stop(self.home_z_joint))
        self.w.btn_jog_zminus.pressed.connect(lambda: self.jog_joint(self.home_z_joint, -1))
        self.w.btn_jog_zminus.released.connect(lambda: self.jog_stop(self.home_z_joint))
        
        # Connect spindle controls
        self.w.slider_spindle_speed.valueChanged.connect(self.update_spindle_speed_display)
        self.w.btn_spindle_fwd.clicked.connect(self.spindle_forward)
        self.w.btn_spindle_stop.clicked.connect(self.spindle_stop)
        self.w.btn_spindle_rev.clicked.connect(self.spindle_reverse)
        
        # Connect override sliders
        self.w.slider_feedrate.valueChanged.connect(self.update_feedrate_override)
        self.w.slider_rapidrate.valueChanged.connect(self.update_rapid_override)
        
        # Initialize displays - use our INI-configured values
        # The sliders were already set correctly in setup_*_controls_dynamic()
        self.update_spindle_speed_display(self.spindle_speed)
        self.update_jog_velocity(self.jog_speed)
        
        # Start in MANUAL mode - show manual controls, hide MDI and Auto
        self.w.stackedWidget_modes.setCurrentIndex(0)  # Show page_manual
        self.w.btn_mode_manual.setChecked(True)
        
        # Setup periodic status update timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.periodic_update)
        self.timer.start(100)  # 100ms update rate
        
        # Setup keyboard shortcuts that trigger jog button signals
        self.shortcut_x_plus = QShortcut(QKeySequence(Qt.Key_Right), self.w)
        self.shortcut_x_plus.activated.connect(lambda: self.w.btn_jog_xplus.pressed.emit())
        self.shortcut_x_plus.setAutoRepeat(False)
        
        self.shortcut_x_minus = QShortcut(QKeySequence(Qt.Key_Left), self.w)
        self.shortcut_x_minus.activated.connect(lambda: self.w.btn_jog_xminus.pressed.emit())
        self.shortcut_x_minus.setAutoRepeat(False)
        
        self.shortcut_y_plus = QShortcut(QKeySequence(Qt.Key_Up), self.w)
        self.shortcut_y_plus.activated.connect(lambda: self.w.btn_jog_yplus.pressed.emit())
        self.shortcut_y_plus.setAutoRepeat(False)
        
        self.shortcut_y_minus = QShortcut(QKeySequence(Qt.Key_Down), self.w)
        self.shortcut_y_minus.activated.connect(lambda: self.w.btn_jog_yminus.pressed.emit())
        self.shortcut_y_minus.setAutoRepeat(False)
        
        # Install key release filter for jog stop
        self.key_release_filter = KeyReleaseFilter(self)
        self.w.installEventFilter(self.key_release_filter)
        
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
    
    def setup_dro_dynamic(self):
        """
        Configure DRO displays dynamically based on machine axes.
        Works for 3-axis, 4-axis, 5+ axis systems.
        """
        print("\n*** CONFIGURING DRO DYNAMICALLY ***")
        
        try:
            # Map of DRO widget names to axis letters
            dro_widgets = {
                'X': 'dro_x',
                'Y': 'dro_y',
                'Z': 'dro_z',
                'A': 'dro_a',  # If exists in UI
                'B': 'dro_b',  # If exists in UI
            }
            
            # Configure each axis that exists in machine config
            for axis_letter in self.machine_config['axes']:
                widget_name = dro_widgets.get(axis_letter)
                
                if widget_name and hasattr(self.w, widget_name):
                    widget = getattr(self.w, widget_name)
                    joint_num = self.axis_to_joint_map.get(axis_letter, 0)
                    
                    # Set joint number
                    widget.setProperty('joint_number', joint_num)
                    widget.setProperty('Qjoint_number', joint_num)
                    widget.setProperty('reference_type', 0)
                    
                    # Set units and template based on metric/imperial
                    if self.is_metric:
                        widget.setProperty('metric_units', True)
                        widget.setProperty('mm_text_template', f'{axis_letter}: %10.3f')
                    else:
                        widget.setProperty('metric_units', False)
                        widget.setProperty('imperial_units', True)
                        widget.setProperty('inch_text_template', f'{axis_letter}: %10.4f')
                    
                    print(f"  ✓ DRO {axis_letter} configured: Joint {joint_num}, Units: {self.machine_config['units_label']}")
            
            print("✓ DRO configuration complete\n")
            
        except Exception as e:
            print(f"⚠ DRO configuration error: {e}")
            print("  Using fallback static configuration\n")
    
    def setup_jog_controls_dynamic(self):
        """
        Configure jog controls based on machine limits and units.
        Sets appropriate slider ranges and default values.
        """
        print("*** CONFIGURING JOG CONTROLS DYNAMICALLY ***")
        
        try:
            # Set jog velocity slider range based on max velocity
            # Range: 0 to max_velocity (in units/sec), converted to units/min for display
            max_jog_speed_per_min = int(self.max_velocity * 60.0)
            
            print(f"  DEBUG: max_velocity = {self.max_velocity} {self.machine_config['units_label']}/s")
            print(f"  DEBUG: max_jog_speed_per_min = {max_jog_speed_per_min}")
            print(f"  DEBUG: self.jog_speed = {self.jog_speed}")
            
            # Get current slider state before modification
            old_min = self.w.slider_jog_velocity.minimum()
            old_max = self.w.slider_jog_velocity.maximum()
            old_val = self.w.slider_jog_velocity.value()
            print(f"  DEBUG: Slider BEFORE - min:{old_min}, max:{old_max}, value:{old_val}")
            
            # Set new range and value
            self.w.slider_jog_velocity.setMinimum(10)  # Minimum 10 units/min
            self.w.slider_jog_velocity.setMaximum(max_jog_speed_per_min)
            self.w.slider_jog_velocity.setValue(self.jog_speed)
            
            # Verify slider state after modification
            new_min = self.w.slider_jog_velocity.minimum()
            new_max = self.w.slider_jog_velocity.maximum()
            new_val = self.w.slider_jog_velocity.value()
            print(f"  DEBUG: Slider AFTER - min:{new_min}, max:{new_max}, value:{new_val}")
            
            print(f"  ✓ Jog velocity slider: {new_min} to {new_max} {self.machine_config['units_label']}/min")
            print(f"  ✓ Default jog speed: {new_val} {self.machine_config['units_label']}/min")
            print(f"  ✓ Jog increments available: {self.jog_increments} {self.machine_config['units_label']}")
            print("✓ Jog controls configured\n")
            
        except Exception as e:
            print(f"⚠ Jog control configuration error: {e}")
            import traceback
            traceback.print_exc()
            print()
    
    def setup_spindle_controls_dynamic(self):
        """
        Configure spindle controls based on INI max spindle speed.
        Sets slider range and default value.
        """
        print("*** CONFIGURING SPINDLE CONTROLS DYNAMICALLY ***")
        
        try:
            max_spindle = int(self.machine_config.get('max_spindle_speed', 24000))
            
            print(f"  DEBUG: max_spindle_speed from config = {max_spindle}")
            print(f"  DEBUG: self.spindle_speed = {self.spindle_speed}")
            
            # Get current slider state
            old_min = self.w.slider_spindle_speed.minimum()
            old_max = self.w.slider_spindle_speed.maximum()
            old_val = self.w.slider_spindle_speed.value()
            print(f"  DEBUG: Slider BEFORE - min:{old_min}, max:{old_max}, value:{old_val}")
            
            # Set new range and value
            self.w.slider_spindle_speed.setMinimum(0)
            self.w.slider_spindle_speed.setMaximum(max_spindle)
            self.w.slider_spindle_speed.setValue(self.spindle_speed)
            
            # Verify slider state
            new_min = self.w.slider_spindle_speed.minimum()
            new_max = self.w.slider_spindle_speed.maximum()
            new_val = self.w.slider_spindle_speed.value()
            print(f"  DEBUG: Slider AFTER - min:{new_min}, max:{new_max}, value:{new_val}")
            
            print(f"  ✓ Spindle speed slider: {new_min} to {new_max} RPM")
            print(f"  ✓ Default spindle speed: {new_val} RPM")
            print("✓ Spindle controls configured\n")
            
        except Exception as e:
            print(f"⚠ Spindle control configuration error: {e}")
            import traceback
            traceback.print_exc()
            print()
    
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
            
            # Update velocity display
            self.update_velocity_display()
            
            # Update E-stop button appearance
            if STATUS.estop_is_clear():
                self.w.btn_estop.setText("E-STOP\nCLEAR")
                self.w.btn_estop.setStyleSheet("""
                    QPushButton {
                        background-color: #27ae60;
                        color: white;
                        border: 2px solid #1e8449;
                        font-weight: bold;
                        border-radius: 4px;
                    }
                """)
            else:
                self.w.btn_estop.setText("E-STOP\nACTIVE")
                self.w.btn_estop.setStyleSheet("""
                    QPushButton {
                        background-color: #c0392b;
                        color: white;
                        border: 2px solid #943126;
                        font-weight: bold;
                        border-radius: 4px;
                    }
                """)
            
            # Update power button appearance
            if STATUS.machine_is_on():
                self.w.btn_power.setText("POWER\nON")
                self.w.btn_power.setStyleSheet("""
                    QPushButton {
                        background-color: #27ae60;
                        color: white;
                        border: 2px solid #1e8449;
                        font-weight: bold;
                        border-radius: 4px;
                    }
                """)
            else:
                self.w.btn_power.setText("POWER\nOFF")
                self.w.btn_power.setStyleSheet("""
                    QPushButton {
                        background-color: #7f8c8d;
                        color: white;
                        border: 2px solid #5d6d7e;
                        font-weight: bold;
                        border-radius: 4px;
                    }
                """)
            
            # Update program line highlight in AUTO mode
            if self.current_mode == "AUTO" and self.loaded_program_lines:
                current_line = self.stat.motion_line
                if current_line != self.last_highlighted_line:
                    self.highlight_gcode_line(current_line)
                    self.last_highlighted_line = current_line
            
        except Exception as e:
            pass
    
    def update_velocity_display(self):
        """Update velocity display in DRO - called every 100ms from periodic_update"""
        try:
            # Check if dro_velocity widget exists in UI
            if not hasattr(self.w, 'dro_velocity'):
                return
            
            # Get current actual velocity from LinuxCNC stat
            # stat.current_vel = magnitude of velocity vector (units/sec)
            # This is actual machine velocity, not commanded velocity
            velocity = 0.0
            
            if hasattr(self.stat, 'current_vel'):
                # Preferred: LinuxCNC provides computed velocity magnitude
                velocity = self.stat.current_vel
            else:
                # Fallback: compute magnitude from joint velocities
                # stat.joint_velocity = array of joint velocities (units/sec)
                if hasattr(self.stat, 'joint_velocity') and self.stat.joint_velocity:
                    import math
                    # Velocity magnitude: sqrt(vx² + vy² + vz² + ...)
                    sum_squares = sum(v * v for v in self.stat.joint_velocity)
                    velocity = math.sqrt(sum_squares)
            
            # Convert units/sec → units/min for display
            velocity_per_min = abs(velocity * 60.0)
            
            # Get units label from machine config (mm or in)
            units_label = self.machine_config.get('units_label', 'mm')
            
            # Update DRO velocity widget
            self.w.dro_velocity.setText(f"Vel: {velocity_per_min:.1f} {units_label}/min")
            
        except Exception:
            # Graceful fallback on any error - display zero velocity
            try:
                if hasattr(self.w, 'dro_velocity'):
                    units_label = self.machine_config.get('units_label', 'mm')
                    self.w.dro_velocity.setText(f"Vel: 0.0 {units_label}/min")
            except:
                pass  # Silent fail - don't crash periodic_update
    
    def is_auto_running(self):
        """Check if auto mode is running"""
        try:
            self.stat.poll()
            return self.stat.task_mode == linuxcnc.MODE_AUTO and (
                self.stat.interp_state == linuxcnc.INTERP_READING or
                self.stat.interp_state == linuxcnc.INTERP_WAITING
            )
        except:
            return False
    
    def execute_mdi(self):
        """Execute MDI command"""
        if self.current_mode != "MDI":
            return
        
        command = self.w.text_mdi_input.text().strip()
        if not command:
            return
        
        print(f"Executing MDI: {command}")
        
        try:
            self.command.mode(linuxcnc.MODE_MDI)
            self.command.wait_complete()
            self.command.mdi(command)
            
            # Add to history
            self.w.text_mdi_history.append(f"> {command}")
            self.w.text_mdi_input.clear()
            
        except Exception as e:
            print(f"MDI error: {e}")
            self.w.text_mdi_history.append(f"ERROR: {e}")
    
    def clear_mdi(self):
        """Clear MDI history"""
        self.w.text_mdi_history.clear()
        print("MDI history cleared")
    
    def load_program(self):
        """Load G-code program"""
        file_path, _ = QFileDialog.getOpenFileName(
            self.w,
            "Load G-Code Program",
            os.path.expanduser("~"),
            "G-Code Files (*.ngc *.nc *.tap);;All Files (*.*)"
        )
        
        if not file_path:
            return
        
        print(f"\n*** LOADING PROGRAM ***")
        print(f"File: {file_path}")
        
        try:
            # Load file into LinuxCNC
            self.command.mode(linuxcnc.MODE_AUTO)
            self.command.wait_complete()
            self.command.program_open(file_path)
            
            # Store path
            self.loaded_program_path = file_path
            
            # Read and display program
            with open(file_path, 'r') as f:
                self.loaded_program_lines = f.readlines()
            
            self.w.text_gcode_preview.clear()
            for i, line in enumerate(self.loaded_program_lines, 1):
                self.w.text_gcode_preview.append(f"{i:4d} | {line.rstrip()}")
            
            # Update loaded filename label if it exists
            if hasattr(self.w, 'label_11'):
                self.w.label_11.setText(f"Loaded: {os.path.basename(file_path)}")
            
            print(f"✓ Program loaded: {len(self.loaded_program_lines)} lines")
            print("="*25 + "\n")
            
        except Exception as e:
            print(f"Load error: {e}")
            self.loaded_program_path = None
            self.loaded_program_lines = []
    
    def cycle_start(self):
        """Start program execution"""
        if not self.loaded_program_path:
            print("ERROR: No program loaded!")
            return
        
        if not STATUS.machine_is_on():
            print("ERROR: Power OFF!")
            return
        
        print("\n*** CYCLE START ***")
        try:
            self.command.mode(linuxcnc.MODE_AUTO)
            self.command.wait_complete()
            self.command.auto(linuxcnc.AUTO_RUN, 0)
            print("✓ Program started")
        except Exception as e:
            print(f"Start error: {e}")
    
    def pause_program(self):
        """Pause program execution"""
        print("Program PAUSED")
        try:
            self.command.auto(linuxcnc.AUTO_PAUSE)
        except Exception as e:
            print(f"Pause error: {e}")
    
    def stop_program(self):
        """Stop program execution"""
        print("Program STOPPED")
        try:
            self.command.abort()
        except Exception as e:
            print(f"Stop error: {e}")
    
    def highlight_gcode_line(self, line_number):
        """Highlight current G-code line"""
        if line_number < 0 or line_number >= len(self.loaded_program_lines):
            return
        
        cursor = self.w.text_gcode_preview.textCursor()
        cursor.movePosition(QTextCursor.Start)
        cursor.movePosition(QTextCursor.Down, QTextCursor.MoveAnchor, line_number)
        
        # Clear previous highlight
        self.w.text_gcode_preview.setExtraSelections([])
        
        # Set new highlight
        selection = QTextCursor(cursor)
        selection.select(QTextCursor.LineUnderCursor)
        
        fmt = QTextCharFormat()
        fmt.setBackground(QColor("#3498db"))
        fmt.setForeground(QColor("white"))
        
        extra_selection = type('obj', (object,), {
            'cursor': selection,
            'format': fmt
        })()
        
        self.w.text_gcode_preview.setExtraSelections([extra_selection])
    
    def set_jog_increment(self, value):
        """Set jog increment mode"""
        if value == "continuous":
            self.jog_mode = "continuous"
            print(f"Jog mode: CONTINUOUS")
        else:
            self.jog_mode = "increment"
            self.jog_increment = value
            print(f"Jog mode: INCREMENT {value} {self.machine_config['units_label']}")
    
    def update_jog_velocity(self, value):
        """Update jog velocity"""
        self.jog_speed = value
        # Update jog velocity label if it exists
        if hasattr(self.w, 'label_jog_2'):
            self.w.label_jog_2.setText(f"Jog Velocity: {value}{self.machine_config['units_label']}/min")
        elif hasattr(self.w, 'label_jog_velocity'):
            self.w.label_jog_velocity.setText(f"Jog: {value} {self.machine_config['units_label']}/min")
    
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
            
            # Unhome all joints first
            for joint_num in range(self.machine_config['joint_count']):
                if self.stat.homed[joint_num] == 1:
                    self.command.unhome(joint_num)
            
            self.command.wait_complete()
            
            # Home all joints
            for joint_num in range(self.machine_config['joint_count']):
                self.command.home(joint_num)
            
            print(f"✓ Homing complete for {self.machine_config['joint_count']} joints")
            print(f"Axes: {' '.join(self.machine_config['axes'])}")
        except Exception as e:
            print(f"Homing error: {e}")
        print("="*25 + "\n")
    
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
    
    def open_joint_assignment_dialog(self):
        """Open dialog to reassign joints to home buttons"""
        # Get current mappings
        current_mappings = {
            'x': self.home_x_joint,
            'y': self.home_y_joint,
            'z': self.home_z_joint
        }
        
        # Get joint count from machine config
        joint_count = self.machine_config['joint_count']
        
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
                
                # Reconnect jog buttons with new joint assignments
                self.reconnect_jog_buttons()
        else:
            print("Joint assignment cancelled")
    
    def reconnect_jog_buttons(self):
        """Reconnect jog buttons after joint reassignment"""
        print("Reconnecting jog buttons to new joint assignments...")
        
        # Disconnect old connections (if possible - PyQt doesn't easily support this)
        # Instead, we'll rely on the lambda capturing the current joint values
        
        # Reconnect with new joint assignments
        self.w.btn_jog_xplus.pressed.disconnect()
        self.w.btn_jog_xplus.released.disconnect()
        self.w.btn_jog_xminus.pressed.disconnect()
        self.w.btn_jog_xminus.released.disconnect()
        
        self.w.btn_jog_yplus.pressed.disconnect()
        self.w.btn_jog_yplus.released.disconnect()
        self.w.btn_jog_yminus.pressed.disconnect()
        self.w.btn_jog_yminus.released.disconnect()
        
        self.w.btn_jog_zplus.pressed.disconnect()
        self.w.btn_jog_zplus.released.disconnect()
        self.w.btn_jog_zminus.pressed.disconnect()
        self.w.btn_jog_zminus.released.disconnect()
        
        # Reconnect with new mappings
        self.w.btn_jog_xplus.pressed.connect(lambda: self.jog_joint(self.home_x_joint, 1))
        self.w.btn_jog_xplus.released.connect(lambda: self.jog_stop(self.home_x_joint))
        self.w.btn_jog_xminus.pressed.connect(lambda: self.jog_joint(self.home_x_joint, -1))
        self.w.btn_jog_xminus.released.connect(lambda: self.jog_stop(self.home_x_joint))
        
        self.w.btn_jog_yplus.pressed.connect(lambda: self.jog_joint(self.home_y_joint, 1))
        self.w.btn_jog_yplus.released.connect(lambda: self.jog_stop(self.home_y_joint))
        self.w.btn_jog_yminus.pressed.connect(lambda: self.jog_joint(self.home_y_joint, -1))
        self.w.btn_jog_yminus.released.connect(lambda: self.jog_stop(self.home_y_joint))
        
        self.w.btn_jog_zplus.pressed.connect(lambda: self.jog_joint(self.home_z_joint, 1))
        self.w.btn_jog_zplus.released.connect(lambda: self.jog_stop(self.home_z_joint))
        self.w.btn_jog_zminus.pressed.connect(lambda: self.jog_joint(self.home_z_joint, -1))
        self.w.btn_jog_zminus.released.connect(lambda: self.jog_stop(self.home_z_joint))
        
        print("✓ Jog buttons reconnected")
    
    def jog_joint(self, joint_num, direction):
        """Start jogging - uses machine-specific velocity limits"""
        if self.current_mode != "MANUAL":
            return
        
        if not STATUS.machine_is_on() or not STATUS.estop_is_clear():
            return
        
        # Get max velocity for this specific joint (safety check)
        if joint_num < len(self.machine_config['joint_max_velocities']):
            joint_max_vel = self.machine_config['joint_max_velocities'][joint_num]
        else:
            joint_max_vel = self.max_velocity
        
        # Convert jog speed from units/min to units/sec
        speed_per_sec = self.jog_speed / 60.0
        
        # Clamp to joint's max velocity
        speed_per_sec = min(speed_per_sec, joint_max_vel)
        
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
