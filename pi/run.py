import os
import sys
import glob
import logging
from joint_controller import JointController
from motion_controller import MotionController

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

FIRMWARE_DATA_DIR = os.path.join(os.path.dirname(__file__), '../firmware/data')

def list_motions():
    pattern = os.path.join(FIRMWARE_DATA_DIR, '*.json')
    files = sorted(glob.glob(pattern))
    return files

def main():
    logger.info("Initializing PLEN Control for NanoPi Duo...")
    
    # Initialize Controllers
    try:
        joint_ctrl = JointController()
        motion_ctrl = MotionController(joint_ctrl)
    except Exception as e:
        logger.error(f"Failed to initialize controllers: {e}")
        return

    logger.info("Initialization Complete.")

    if len(sys.argv) > 1:
        motion_file = sys.argv[1]
        speed = 1.0
        if len(sys.argv) > 2:
            try:
                speed = float(sys.argv[2])
            except ValueError:
                logger.error("Invalid speed argument. Using default 1.0")

        if os.path.exists(motion_file):
            logger.info(f"Playing provided motion file: {motion_file} at {speed}x speed")
            motion_ctrl.play(motion_file, speed)
        else:
            logger.error(f"File not found: {motion_file}")
    else:
        # Interactive Mode
        motions = list_motions()
        if not motions:
            logger.warning(f"No motion files found in {FIRMWARE_DATA_DIR}")
            return

        print("\nAvailable Motions:")
        for i, f in enumerate(motions):
            name = os.path.basename(f)
            print(f"{i}: {name}")
        
        print("\nEnter number to play (optionally followed by speed, e.g. '0 2.0'), or 'q' to quit.")
        
        while True:
            try:
                choice = input("> ").strip()
                if choice.lower() == 'q':
                    break
                
                parts = choice.split()
                if not parts:
                    continue
                    
                idx = int(parts[0])
                speed = 1.0
                if len(parts) > 1:
                    speed = float(parts[1])

                if 0 <= idx < len(motions):
                    selected = motions[idx]
                    logger.info(f"Playing {os.path.basename(selected)} at {speed}x speed...")
                    motion_ctrl.play(selected, speed)
                    logger.info("Done.")
                else:
                    print("Invalid selection.")
            except ValueError:
                print("Please enter a valid number (and optional speed) or 'q'.")
            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except Exception as e:
                logger.error(f"Error: {e}")

if __name__ == "__main__":
    main()
