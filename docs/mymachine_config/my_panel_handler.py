#!/usr/bin/env python3
"""
QtVCP Panel Handler - Mode-Based Visibility Control
Version: 6.0 - REORGANIZED LAYOUT WITH STRICT MODE VISIBILITY
"""

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QButtonGroup, QFileDialog
from PyQt5.QtGui import QTextCursor, QTextCharFormat, QColor
from qtvcp.core import Status, Action, Info
import linuxcnc
import os
import time

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
        
    def initialized__(self):
        """Called after widgets are initialized"""
        print("="*50)
        print("QtVCP Panel - Mode-Based Visibility Control")
        print("Version 6.0 - REORGANIZED LAYOUT")
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
        
        print("\n*** STARTUP SEQUENCE ***")
        print("1. Click E-STOP to clear")
        print("2. Click POWER ON")
        print("3. Click HOME ALL")
        print("4. Select mode:")
        print("   - MANUAL MODE: Jog controls + Spindle + Overrides visible")
        print("   - MDI MODE: MDI command input visible")
        print("   - AUTO MODE: Program loader + execution controls visible")
        print("\n*** MODE-BASED VISIBILITY ***")
        print("✓ Manual: Jog buttons + Spindle/Override (right panel)")
        print("✓ MDI: MDI controls only (right panel)")
        print("✓ Auto: Program loader + controls (right panel)")
        print("✓ Constant: DRO, Mode buttons, E-STOP, POWER, HOME (always visible)")
        print("="*50 + "\n")
    
    def setup_dro(self):
        """Configure DRO displays"""
        try:
            for dro, joint in [(self.w.dro_x, 0), (self.w.dro_y, 1), (self.w.dro_z, 2)]:
                dro.setProperty('joint_number', joint)
                dro.setProperty('Qjoint_number', joint)
                dro.setProperty('reference_type', 0)
                dro.setProperty('metric_units', True)
                dro.setProperty('mm_text_template', '%10.3f')
            print("✓ DRO configured (X, Y, Z)")
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
        print("VISIBLE: MDI command input, Execute, Clear, History")
        print("HIDDEN: Jog controls, Spindle controls, Auto controls")
        
        # Switch stacked widget to MDI page (index 1)
        # This automatically hides manual controls and shows MDI controls
        self.w.stackedWidget_modes.setCurrentIndex(1)
        
        # Set LinuxCNC to MDI mode
        try:
            self.command.mode(linuxcnc.MODE_MDI)
            self.command.wait_complete()
            print("✓ MDI mode ready - Enter G-code commands")
        except Exception as e:
            print(f"Mode switch error: {e}")
        
        # Check if homed
        self.stat.poll()
        all_homed = all(self.stat.homed[i] == 1 for i in range(INFO.JOINT_COUNT))
        if not all_homed:
            print("\n" + "="*50)
            print("⚠ WARNING: NOT ALL AXES HOMED!")
            print("MDI commands may be rejected by LinuxCNC")
            print("Recommendation: Click HOME ALL first")
            print("="*50 + "\n")
    
    def switch_to_auto(self):
        """Switch to AUTO mode - Show program loader + execution controls in right panel"""
        # Safety check - prevent mode switch during program execution
        if self.is_auto_running():
            print("ERROR: Cannot change mode - already running!")
            return
        
        if not STATUS.machine_is_on():
            print("ERROR: Cannot switch to AUTO - Power is OFF!")
            print("Click POWER ON first")
            self.w.btn_mode_manual.setChecked(True)
            return
        
        self.current_mode = "AUTO"
        print("\n*** AUTO MODE ACTIVATED ***")
        print("VISIBLE: Load Program, Program Preview, Cycle Start, Pause, Stop")
        print("HIDDEN: Jog controls, Spindle controls, MDI controls")
        
        # Switch stacked widget to Auto page (index 2)
        # This automatically hides manual and MDI controls
        self.w.stackedWidget_modes.setCurrentIndex(2)
        
        # Set LinuxCNC to auto mode
        try:
            self.command.mode(linuxcnc.MODE_AUTO)
            self.command.wait_complete()
            print("✓ AUTO mode ready - Load a G-code program")
        except Exception as e:
            print(f"Mode switch error: {e}")
        
        # Check if homed
        self.stat.poll()
        all_homed = all(self.stat.homed[i] == 1 for i in range(INFO.JOINT_COUNT))
        if not all_homed:
            print("\n" + "="*50)
            print("⚠ WARNING: NOT ALL AXES HOMED!")
            print("Program execution may be rejected by LinuxCNC")
            print("Recommendation: Click HOME ALL first")
            print("="*50 + "\n")
    
    def is_auto_running(self):
        """Check if auto mode is running"""
        try:
            self.stat.poll()
            return (self.stat.task_mode == linuxcnc.MODE_AUTO and 
                    self.stat.interp_state != linuxcnc.INTERP_IDLE)
        except:
            return False
    
    def load_program(self):
        """Load a G-code program"""
        if not STATUS.machine_is_on():
            print("ERROR: Power OFF!")
            return
        
        # Check if already running
        if self.is_auto_running():
            print("ERROR: Program is already running!")
            return
        
        file_path, _ = QFileDialog.getOpenFileName(
            None,
            "Select G-code Program",
            os.path.expanduser("~"),
            "G-code Files (*.ngc *.nc *.gcode);;All Files (*)"
        )
        
        if not file_path:
            print("Load cancelled")
            return
        
        print("\n" + "="*50)
        print(f"LOADING PROGRAM: {os.path.basename(file_path)}")
        print("="*50)
        
        try:
            # Load program into LinuxCNC
            self.command.mode(linuxcnc.MODE_AUTO)
            self.command.wait_complete()
            self.command.program_open(file_path)
            
            # Read program for preview
            with open(file_path, 'r') as f:
                self.loaded_program_lines = f.readlines()
            
            # Display in preview
            preview_text = ''.join(self.loaded_program_lines)
            self.w.text_program_preview.setPlainText(preview_text)
            
            # Update label
            self.w.label_11.setText(f"Loaded: {os.path.basename(file_path)}")
            
            self.loaded_program_path = file_path
            print(f"✓ Program loaded successfully")
            print(f"✓ {len(self.loaded_program_lines)} lines")
            print("✓ Click CYCLE START to begin execution")
            print("="*50 + "\n")
            
        except Exception as e:
            print(f"✗ Load error: {e}")
            print("="*50 + "\n")
    
    def cycle_start(self):
        """Start program execution"""
        if not self.loaded_program_path:
            print("ERROR: No program loaded!")
            return
        
        if not STATUS.machine_is_on():
            print("ERROR: Power OFF!")
            return
        
        print("\n" + "="*50)
        print("CYCLE START - Program execution beginning")
        print("="*50)
        
        try:
            self.command.mode(linuxcnc.MODE_AUTO)
            self.command.wait_complete()
            self.command.auto(linuxcnc.AUTO_RUN, 0)
            print("✓ Program running")
            print("Watch DRO for position changes")
            print("="*50 + "\n")
        except Exception as e:
            print(f"✗ Cycle start error: {e}")
            print("="*50 + "\n")
    
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
    
    def periodic_update(self):
        """Periodic status updates"""
        try:
            self.stat.poll()
            
            # Update state label
            state_text = {
                linuxcnc.STATE_ESTOP: "E-STOP",
                linuxcnc.STATE_ESTOP_RESET: "RESET",
                linuxcnc.STATE_OFF: "OFF",
                linuxcnc.STATE_ON: "READY"
            }.get(self.stat.task_state, "UNKNOWN")
            
            self.w.label_state.setText(f"State: {state_text}")
            
            # Update line number in auto mode
            if self.current_mode == "AUTO":
                self.w.label_line.setText(f"Line: {self.stat.motion_line:03d}")
                
                # Highlight current line in program preview
                current_line = self.stat.motion_line
                if current_line != self.last_highlighted_line and current_line > 0:
                    self.highlight_program_line(current_line)
                    self.last_highlighted_line = current_line
        except:
            pass
    
    def highlight_program_line(self, line_num):
        """Highlight current line in program preview"""
        try:
            cursor = self.w.text_program_preview.textCursor()
            cursor.movePosition(QTextCursor.Start)
            
            # Move to target line
            for _ in range(line_num - 1):
                cursor.movePosition(QTextCursor.Down)
            
            # Select the line
            cursor.select(QTextCursor.LineUnderCursor)
            
            # Apply highlight
            fmt = QTextCharFormat()
            fmt.setBackground(QColor("#ffff00"))
            fmt.setForeground(QColor("#000000"))
            cursor.setCharFormat(fmt)
            
            # Scroll to line
            self.w.text_program_preview.setTextCursor(cursor)
            self.w.text_program_preview.ensureCursorVisible()
        except:
            pass
    
    def execute_mdi(self):
        """Execute MDI command"""
        if self.current_mode != "MDI":
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
