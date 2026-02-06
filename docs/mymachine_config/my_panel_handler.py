#!/usr/bin/env python3
"""
QtVCP Panel Handler
Handles machine control and jog functionality
"""

from PyQt5.QtCore import Qt, QTimer
from qtvcp.core import Status, Action, Info
import linuxcnc

STATUS = Status()
ACTION = Action()
INFO = Info()

class HandlerClass:
    def __init__(self, halcomp, widgets, paths):
        self.hal = halcomp
        self.w = widgets
        self.jog_speed = 100  # mm/min
        self.command = linuxcnc.command()
        self.stat = linuxcnc.stat()
        
    def initialized__(self):
        """Called after widgets are initialized"""
        print("QtVCP Panel Initialized!")
        
        # Connect machine control buttons
        self.w.btn_estop.clicked.connect(self.toggle_estop)
        self.w.btn_power.clicked.connect(self.toggle_power)
        self.w.btn_home_all.clicked.connect(self.home_all)
        
        # Connect jog button signals
        # X axis (Joint 0)
        self.w.btn_jog_xplus.pressed.connect(lambda: self.jog_joint(0, 1))
        self.w.btn_jog_xplus.released.connect(lambda: self.jog_stop(0))
        
        self.w.btn_jog_xminus.pressed.connect(lambda: self.jog_joint(0, -1))
        self.w.btn_jog_xminus.released.connect(lambda: self.jog_stop(0))
        
        # Y axis (Joint 1)
        self.w.btn_jog_yplus.pressed.connect(lambda: self.jog_joint(1, 1))
        self.w.btn_jog_yplus.released.connect(lambda: self.jog_stop(1))
        
        self.w.btn_jog_yminus.pressed.connect(lambda: self.jog_joint(1, -1))
        self.w.btn_jog_yminus.released.connect(lambda: self.jog_stop(1))
        
        # Z axis (Joint 2)
        self.w.btn_jog_zplus.pressed.connect(lambda: self.jog_joint(2, 1))
        self.w.btn_jog_zplus.released.connect(lambda: self.jog_stop(2))
        
        self.w.btn_jog_zminus.pressed.connect(lambda: self.jog_joint(2, -1))
        self.w.btn_jog_zminus.released.connect(lambda: self.jog_stop(2))
        
        print("All buttons connected successfully")
        print("\n=== STARTUP SEQUENCE ===")
        print("1. Click 'E-STOP' to clear E-stop")
        print("2. Click 'POWER ON' to enable machine")
        print("3. Click 'HOME ALL' to home all axes (moves to 0,0,0)")
        print("4. Now you can use JOG buttons")
        print("5. Click 'HOME ALL' anytime to return to home position")
        print("========================\n")
    
    def toggle_estop(self):
        """Toggle E-stop state"""
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
                print("ERROR: Cannot turn on power - E-stop is active!")
                print("Click E-STOP button first to clear it")
                return
            print("Machine POWER ON")
            ACTION.SET_MACHINE_STATE(True)
        
    def home_all(self):
        """Home all axes - moves them to home position (can be called multiple times)"""
        # Check if machine is ready to home
        if not STATUS.estop_is_clear():
            print("ERROR: Cannot home - E-stop is active!")
            print("Click E-STOP button first")
            return
            
        if not STATUS.machine_is_on():
            print("ERROR: Cannot home - Machine power is OFF!")
            print("Click POWER ON button first")
            return
        
        print("\n=== HOMING ALL AXES ===")
        
        try:
            # Update status
            self.stat.poll()
            
            # Switch to manual mode
            self.command.mode(linuxcnc.MODE_MANUAL)
            self.command.wait_complete()
            
            # First, UNHOME all joints if they are already homed
            # This allows us to home again
            num_joints = INFO.JOINT_COUNT
            
            for joint_num in range(num_joints):
                if self.stat.homed[joint_num] == 1:
                    print(f"  Unhoming Joint {joint_num}...")
                    self.command.unhome(joint_num)
            
            # Small delay to ensure unhoming completes
            self.command.wait_complete()
            
            # Now HOME all joints - they will move to home position
            print("Moving axes to home position (0, 0, 0)...")
            for joint_num in range(num_joints):
                print(f"  Homing Joint {joint_num}...")
                self.command.home(joint_num)
            
            print("Homing initiated - axes moving to home position")
            print("You can press HOME ALL again anytime to return home")
            
        except Exception as e:
            print(f"Error during homing: {e}")
            # Fallback method
            try:
                print("Trying fallback homing method...")
                ACTION.SET_MACHINE_UNHOMED(-1)  # Unhome all
                QTimer.singleShot(100, lambda: ACTION.SET_MACHINE_HOMING(-1))  # Home all after delay
            except Exception as e2:
                print(f"Fallback also failed: {e2}")
        
        print("======================\n")
    
    def jog_joint(self, joint_num, direction):
        """Start jogging a joint in the specified direction"""
        axis_names = ['X', 'Y', 'Z']
        axis_name = axis_names[joint_num] if joint_num < 3 else str(joint_num)
        
        # Check if machine is ready
        if not STATUS.machine_is_on():
            print(f"Cannot jog - Machine is not powered on!")
            return
        if not STATUS.estop_is_clear():
            print(f"Cannot jog - E-stop is active!")
            return
        
        # Check if joint is homed
        try:
            self.stat.poll()
            if self.stat.homed[joint_num] == 0:
                print(f"WARNING: {axis_name} axis (Joint {joint_num}) is not homed!")
                print("Recommend homing the machine first using HOME ALL button")
                # In simulator mode, allow jogging anyway
        except:
            pass
            
        print(f"Jogging {axis_name} (Joint {joint_num}), direction: {direction}, speed: {self.jog_speed}")
        ACTION.JOG(joint_num, direction, self.jog_speed)
        
    def jog_stop(self, joint_num):
        """Stop jogging a joint"""
        axis_names = ['X', 'Y', 'Z']
        axis_name = axis_names[joint_num] if joint_num < 3 else str(joint_num)
        print(f"Stopping {axis_name} (Joint {joint_num}) jog")
        ACTION.JOG(joint_num, 0, 0)

def get_handlers(halcomp, widgets, paths):
    """Required function to return handler instances"""
    return [HandlerClass(halcomp, widgets, paths)]
