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
        if os.path.exists(motion_file):
            logger.info(f"Playing provided motion file: {motion_file}")
            motion_ctrl.play(motion_file)
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
        
        print("\nEnter number to play, or 'q' to quit.")
        
        while True:
            try:
                choice = input("> ")
                if choice.lower() == 'q':
                    break
                
                idx = int(choice)
                if 0 <= idx < len(motions):
                    selected = motions[idx]
                    logger.info(f"Playing {os.path.basename(selected)}...")
                    motion_ctrl.play(selected)
                    logger.info("Done.")
                else:
                    print("Invalid selection.")
            except ValueError:
                print("Please enter a number or 'q'.")
            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except Exception as e:
                logger.error(f"Error: {e}")

if __name__ == "__main__":
    main()
