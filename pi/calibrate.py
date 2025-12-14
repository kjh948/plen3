import sys
import tty
import termios
import os
import logging
from joint_controller import JointController

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_char():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
        if ch == '\x1b':  # Arrow keys usually start with ESC [
            ch2 = sys.stdin.read(1)
            if ch2 == '[':
                ch3 = sys.stdin.read(1)
                return ch + ch2 + ch3
            return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch

def print_menu(controller):
    os.system('clear')
    print("=== PLEN Servo Calibration ===")
    print("Select a joint to calibrate:")
    
    # Sort by ID
    ids = sorted(controller.SERVO_MAP.keys())
    
    # Group by Left/Right roughly based on ID
    print("\n--- Left Side ---")
    for jid in ids:
        if jid < 12 and jid in controller.JOINT_NAMES:
            print(f" {jid}: {controller.JOINT_NAMES[jid]} (Home: {controller.settings[jid]['home']})")
            
    print("\n--- Right Side ---")
    for jid in ids:
        if jid >= 12 and jid in controller.JOINT_NAMES:
            print(f" {jid}: {controller.JOINT_NAMES[jid]} (Home: {controller.settings[jid]['home']})")
            
    print("\ncommands:")
    print(" [ID]: Select joint by number and press Enter (e.g. 1)")
    print(" s: Save configuration")
    print(" q: Quit")

def calibrate_joint(controller, joint_id):
    if joint_id not in controller.JOINT_NAMES:
        print("Invalid Joint ID")
        return

    name = controller.JOINT_NAMES[joint_id]
    step_size = 10
    
    # Move to initial home position
    controller.set_angle(joint_id, controller.settings[joint_id]['home'])

    while True:
        os.system('clear')
        current_home = controller.settings[joint_id]['home']
        print(f"=== Calibrating Joint {joint_id}: {name} ===")
        print(f"Current Home Offset: {current_home}")
        print("\nControls:")
        print(" w / UP Arrow   : Increase (+1)")
        print(" s / DOWN Arrow : Decrease (-1)")
        print(" W (Shift+w)    : Increase (+10)")
        print(" S (Shift+s)    : Decrease (-10)")
        print(" q / ESC        : Return to Menu")
        
        ch = get_char()
        
        delta = 0
        if ch == 'w' or ch == '\x1b[A': # Up
            delta = 1
        elif ch == 's' or ch == '\x1b[B': # Down
            delta = -1
        elif ch == 'W':
            delta = 10
        elif ch == 'S':
            delta = -10
        elif ch == 'q' or ch == '\x1b':
            break
        
        if delta != 0:
            new_home = current_home + delta
            # Constrain if necessary, but usually offsets can be large provided they don't hit physical limits when added to run-time angles.
            # But let's keep it within min/max of the joint logic theoretically, though min/max are usually for runtime.
            # Let's just update it.
            controller.settings[joint_id]['home'] = new_home
            
            # Apply immediately
            # Note: set_angle sets target angle. 
            # If we are calibrating 'home', we effectively want the servo to stay at 'neutral' (0 deg) PLUS the new home offset.
            # So asking it to go to 'Home' means go to 'Neutral' (0) relative to the configuration.
            # Wait, controller.settings['home'] IS the neutral position in PWM ticks? 
            # OR is it an offset?
            # Looking at JointController.cpp:
            # m_SETTINGS[joint_id].HOME = Shared::m_SETTINGS_INITIAL[...]
            # setAngle(joint_id, m_SETTINGS[joint_id].HOME); -> This goes to the home position.
            # So 'home' is a value in "angle units" (approx tenths of degrees) that represents the standing pose?
            # Yes. PLEN's "Home" is the standing pose.
            # So when we calibrate, we want to adjust this 'Home' value so that the robot looks physically correct (e.g. standing straight).
            # So we keep updating set_angle(joint_id, new_home)
            
            controller.set_angle(joint_id, new_home)

def main():
    print("Initializing...")
    try:
        controller = JointController()
    except Exception as e:
        print(f"Error initializing controller: {e}")
        return

    while True:
        print_menu(controller)
        choice = input("\nChoice: ").strip()
        
        if choice == 'q':
            break
        elif choice == 's':
            controller.save_config()
            input("Saved! Press Enter to continue...")
        elif choice.isdigit():
            jid = int(choice)
            if jid in controller.SERVO_MAP:
                calibrate_joint(controller, jid)
            else:
                input("Invalid ID. Press Enter...")
        else:
            pass

if __name__ == "__main__":
    main()
