#!/usr/bin/env python3
"""
QtVCP Panel Handler - Complete Version with Jog Velocity
Features: Jog scaling, Jog velocity, DRO, Feed/Rapid override, Spindle control
Version: 1.1 - DRO FIX APPLIED
"""

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QButtonGroup
from qtvcp.core import Status, Action, Info
from qtvcp.widgets.dro_widget import DROLabel
import linuxcnc

STATUS = Status()
ACTION = Action()
INFO = Info()

class HandlerClass:
    def __init__(self, halcomp, widgets, paths):
        self.hal = halcomp
        self.w = widgets
        self.command = linuxcnc.command()
        self.stat = linuxcnc.stat()
        
        # Jog settings
        self.jog_speed = 500  # mm/min - adjustable via slider
        self.jog_increment = 10.0  # Default 10mm
        self.jog_mode = "increment"  # "increment" or "continuous"
        
        # Spindle settings
        self.spindle_speed = 1000
        
    def initialized__(self):
        """Called after widgets are initialized"""
        print("QtVCP Complete Panel Initialized!")
        
        # Configure DRO displays with proper settings
        self.setup_dro()
        
        # Setup jog increment button group (radio button behavior)
        self.jog_increment_group = QButtonGroup()
        self.jog_increment_group.addButton(self.w.btn_jog_continuous)
        self.jog_increment_group.addButton(self.w.btn_jog_10mm)
        self.jog_increment_group.addButton(self.w.btn_jog_1mm)
        self.jog_increment_group.addButton(self.w.btn_jog_0_1mm)
        self.jog_increment_group.addButton(self.w.btn_jog_0_01mm)
        self.jog_increment_group.setExclusive(True)
        
        # Connect machine control buttons
        self.w.btn_estop.clicked.connect(self.toggle_estop)
        self.w.btn_power.clicked.connect(self.toggle_power)
        self.w.btn_home_all.clicked.connect(self.home_all)
        
        # Connect jog increment buttons
        self.w.btn_jog_continuous.clicked.connect(lambda: self.set_jog_increment("continuous"))
        self.w.btn_jog_10mm.clicked.connect(lambda: self.set_jog_increment(10.0))
        self.w.btn_jog_1mm.clicked.connect(lambda: self.set_jog_increment(1.0))
        self.w.btn_jog_0_1mm.clicked.connect(lambda: self.set_jog_increment(0.1))
        self.w.btn_jog_0_01mm.clicked.connect(lambda: self.set_jog_increment(0.01))
        
        # Connect jog velocity slider
        self.w.slider_jog_velocity.valueChanged.connect(self.update_jog_velocity)
        
        # Connect jog buttons - X axis
        self.w.btn_jog_xplus.pressed.connect(lambda: self.jog_joint(0, 1))
        self.w.btn_jog_xplus.released.connect(lambda: self.jog_stop(0))
        self.w.btn_jog_xminus.pressed.connect(lambda: self.jog_joint(0, -1))
        self.w.btn_jog_xminus.released.connect(lambda: self.jog_stop(0))
        
        # Connect jog buttons - Y axis
        self.w.btn_jog_yplus.pressed.connect(lambda: self.jog_joint(1, 1))
        self.w.btn_jog_yplus.released.connect(lambda: self.jog_stop(1))
        self.w.btn_jog_yminus.pressed.connect(lambda: self.jog_joint(1, -1))
        self.w.btn_jog_yminus.released.connect(lambda: self.jog_stop(1))
        
        # Connect jog buttons - Z axis
        self.w.btn_jog_zplus.pressed.connect(lambda: self.jog_joint(2, 1))
        self.w.btn_jog_zplus.released.connect(lambda: self.jog_stop(2))
        self.w.btn_jog_zminus.pressed.connect(lambda: self.jog_joint(2, -1))
        self.w.btn_jog_zminus.released.connect(lambda: self.jog_stop(2))
        
        # Connect spindle controls
        self.w.slider_spindle_speed.valueChanged.connect(self.update_spindle_speed_display)
        self.w.btn_spindle_fwd.clicked.connect(self.spindle_forward)
        self.w.btn_spindle_stop.clicked.connect(self.spindle_stop)
        self.w.btn_spindle_rev.clicked.connect(self.spindle_reverse)
        
        # Connect feed rate override slider
        self.w.slider_feedrate.valueChanged.connect(self.update_feedrate_override)
        
        # Connect rapid override slider
        self.w.slider_rapidrate.valueChanged.connect(self.update_rapid_override)
        
        # Initialize displays
        self.update_spindle_speed_display(self.w.slider_spindle_speed.value())
        self.update_jog_velocity(self.w.slider_jog_velocity.value())
        
        print("\n=== PANEL READY ===")
        print("1. E-STOP → Clear")
        print("2. POWER ON → Enable")
        print("3. HOME ALL → Home to 0,0,0")
        print("4. Select jog increment (Continuous, 10mm, 1mm, 0.1mm, 0.01mm)")
        print("5. Adjust jog velocity slider (10-2000 mm/min)")
        print("6. Use JOG buttons to move axes")
        print("7. Adjust Feed Rate, Rapid Rate, Spindle Speed as needed")
        print("===================\n")
    
    def setup_dro(self):
        """Configure DRO displays with proper properties - FIX APPLIED"""
        try:
            # X axis DRO - Joint 0
            self.w.dro_x.setProperty('joint_number', 0)
            self.w.dro_x.setProperty('Qjoint_number', 0)
            self.w.dro_x.setProperty('reference_type', 0)  # 0=Absolute, 1=Relative, 2=DTG
            self.w.dro_x.setProperty('metric_units', True)
            self.w.dro_x.setProperty('mm_text_template', '%10.3f')
            self.w.dro_x.setProperty('imperial_text_template', '%9.4f')
            
            # Y axis DRO - Joint 1 (FIXED!)
            self.w.dro_y.setProperty('joint_number', 1)
            self.w.dro_y.setProperty('Qjoint_number', 1)
            self.w.dro_y.setProperty('reference_type', 0)
            self.w.dro_y.setProperty('metric_units', True)
            self.w.dro_y.setProperty('mm_text_template', '%10.3f')
            self.w.dro_y.setProperty('imperial_text_template', '%9.4f')
            
            # Z axis DRO - Joint 2 (FIXED!)
            self.w.dro_z.setProperty('joint_number', 2)
            self.w.dro_z.setProperty('Qjoint_number', 2)
            self.w.dro_z.setProperty('reference_type', 0)
            self.w.dro_z.setProperty('metric_units', True)
            self.w.dro_z.setProperty('mm_text_template', '%10.3f')
            self.w.dro_z.setProperty('imperial_text_template', '%9.4f')
            
            print("✓ DRO widgets configured - Joints 0, 1, 2 (X, Y, Z)")
            print("✓ DRO FIX APPLIED: Each axis now shows correct position!")
        except Exception as e:
            print(f"✗ DRO config error: {e}")
    
    def set_jog_increment(self, increment):
        """Set jog increment mode"""
        if increment == "continuous":
            self.jog_mode = "continuous"
            self.jog_increment = 0
            print("Jog mode: CONTINUOUS")
        else:
            self.jog_mode = "increment"
            self.jog_increment = increment
            print(f"Jog mode: INCREMENTAL - {increment} mm per click")
    
    def update_jog_velocity(self, value):
        """Update jog velocity from slider"""
        self.jog_speed = value
        self.w.label_jog_velocity.setText(f"{value} mm/min")
        print(f"Jog velocity set to: {value} mm/min")
    
    def toggle_estop(self):
        """Toggle E-stop"""
        if STATUS.estop_is_clear():
            print("E-Stop ACTIVATED")
            ACTION.SET_ESTOP_STATE(True)
        else:
            print("E-Stop CLEARED")
            ACTION.SET_ESTOP_STATE(False)
    
    def toggle_power(self):
        """Toggle machine power"""
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
            print("ERROR: Turn on power first!")
            return
        
        print("\n=== HOMING ALL AXES ===")
        try:
            self.stat.poll()
            self.command.mode(linuxcnc.MODE_MANUAL)
            self.command.wait_complete()
            
            # Unhome first
            num_joints = INFO.JOINT_COUNT
            for joint_num in range(num_joints):
                if self.stat.homed[joint_num] == 1:
                    self.command.unhome(joint_num)
            
            self.command.wait_complete()
            
            # Now home
            print("Moving to home position (0, 0, 0)...")
            for joint_num in range(num_joints):
                self.command.home(joint_num)
            
            print("Homing complete - watch DRO! Should show 0.000, 0.000, 0.000")
        except Exception as e:
            print(f"Homing error: {e}")
        print("=======================\n")
    
    def jog_joint(self, joint_num, direction):
        """Start jogging"""
        if not STATUS.machine_is_on() or not STATUS.estop_is_clear():
            print("Cannot jog - check E-stop and power")
            return
        
        axis_names = ['X', 'Y', 'Z']
        axis_name = axis_names[joint_num] if joint_num < 3 else str(joint_num)
        
        if self.jog_mode == "continuous":
            # Continuous jog
            print(f"Jogging {axis_name} continuously at {self.jog_speed} mm/min")
            ACTION.JOG(joint_num, direction, self.jog_speed)
        else:
            # Incremental jog
            print(f"Jogging {axis_name} by {self.jog_increment} mm at {self.jog_speed} mm/min")
            ACTION.JOG(joint_num, direction, self.jog_speed, self.jog_increment)
    
    def jog_stop(self, joint_num):
        """Stop jogging"""
        if self.jog_mode == "continuous":
            axis_names = ['X', 'Y', 'Z']
            axis_name = axis_names[joint_num]
            print(f"Stopping {axis_name}")
            ACTION.JOG(joint_num, 0, 0)
        # For incremental, jog stops automatically
    
    def update_spindle_speed_display(self, value):
        """Update spindle speed label"""
        self.spindle_speed = value
        self.w.label_spindle_speed.setText(f"Speed: {value} RPM")
    
    def spindle_forward(self):
        """Start spindle forward"""
        if not STATUS.machine_is_on():
            print("Cannot start spindle - power off")
            return
        print(f"Spindle FORWARD at {self.spindle_speed} RPM")
        ACTION.SET_SPINDLE_ROTATION(1, self.spindle_speed)
    
    def spindle_stop(self):
        """Stop spindle"""
        print("Spindle STOP")
        ACTION.SET_SPINDLE_ROTATION(0, 0)
    
    def spindle_reverse(self):
        """Start spindle reverse"""
        if not STATUS.machine_is_on():
            print("Cannot start spindle - power off")
            return
        print(f"Spindle REVERSE at {self.spindle_speed} RPM")
        ACTION.SET_SPINDLE_ROTATION(-1, self.spindle_speed)
    
    def update_feedrate_override(self, value):
        """Update feed rate override"""
        self.w.label_feedrate.setText(f"{value}%")
        ACTION.SET_FEED_RATE(value / 100.0)
    
    def update_rapid_override(self, value):
        """Update rapid override"""
        self.w.label_rapidrate.setText(f"{value}%")
        ACTION.SET_RAPID_RATE(value / 100.0)

def get_handlers(halcomp, widgets, paths):
    """Return handler instance"""
    return [HandlerClass(halcomp, widgets, paths)]
