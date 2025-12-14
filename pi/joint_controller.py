import json
import os
import logging
from pca9685_driver import PCA9685

logger = logging.getLogger(__name__)


class JointController:
    # Constants from Firmware
    SUM = 24
    ANGLE_MIN = -800
    ANGLE_MAX = 800
    ANGLE_NEUTRAL = 0
    
    # PWM Settings (for 60Hz 12-bit PCA9685)
    # Original FW: 175 (min), 575 (max), 375 (neutral)
    # These correspond to ticks out of 4096.
    PWM_MIN = 175
    PWM_MAX = 575
    PWM_NEUTRAL = 375
    PWM_FREQ = 60
    
    CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'config.json')

    # Servo Map (Joint ID -> PCA Channel)
    # 0 and 12 are excluded as they were on GPIOs.
    SERVO_MAP = {
        0: 16, # GPIO 12
        1: 7, 2: 6, 3: 5, 4: 4, 5: 3, 6: 2, 7: 1, 8: 0,
        9: 18, 10: 19, 11: 20, # Unused
        12: 17, # GPIO 14
        13: 8, 14: 9, 15: 10, 16: 11, 17: 12, 18: 13, 19: 14, 20: 15,
        21: 21, 22: 22, 23: 23 # Unused
    }
    
    # Names for display
    JOINT_NAMES = {
        0: "Left Shoulder Pitch (Ignored)",
        1: "Left Thigh Yaw",
        2: "Left Shoulder Roll",
        3: "Left Elbow Roll",
        4: "Left Thigh Roll",
        5: "Left Thigh Pitch",
        6: "Left Knee Pitch",
        7: "Left Foot Pitch",
        8: "Left Foot Roll",
        12: "Right Shoulder Pitch (Ignored)",
        13: "Right Thigh Yaw",
        14: "Right Shoulder Roll",
        15: "Right Elbow Roll",
        16: "Right Thigh Roll",
        17: "Right Thigh Pitch",
        18: "Right Knee Pitch",
        19: "Right Foot Pitch",
        20: "Right Foot Roll"
    }

    # Initial Settings (Min, Max, Home)
    # Copied from JointController.cpp Shared::m_SETTINGS_INITIAL
    # Format: [MIN, MAX, HOME] for each joint 0..23
    SETTINGS_INITIAL = [
        [ANGLE_MIN, ANGLE_MAX, -40],  # 00 Left Shoulder Pitch
        [ANGLE_MIN, ANGLE_MAX, 245],  # 01 Left Thigh Yaw
        [ANGLE_MIN, ANGLE_MAX, 470],  # 02 Left Shoulder Roll
        [ANGLE_MIN, ANGLE_MAX, -100], # 03 Left Elbow Roll
        [ANGLE_MIN, ANGLE_MAX, -205], # 04 Left Thigh Roll
        [ANGLE_MIN, ANGLE_MAX, 50],   # 05 Left Thigh Pitch
        [ANGLE_MIN, ANGLE_MAX, 445],  # 06 Left Knee Pitch
        [ANGLE_MIN, ANGLE_MAX, 245],  # 07 Left Foot Pitch
        [ANGLE_MIN, ANGLE_MAX, -75],  # 08 Left Foot Roll
        [ANGLE_MIN, ANGLE_MAX, ANGLE_NEUTRAL], # 09
        [ANGLE_MIN, ANGLE_MAX, ANGLE_NEUTRAL], # 10
        [ANGLE_MIN, ANGLE_MAX, ANGLE_NEUTRAL], # 11
        [ANGLE_MIN, ANGLE_MAX, 15],   # 12 Right Shoulder Pitch
        [ANGLE_MIN, ANGLE_MAX, -70],  # 13 Right Thigh Yaw
        [ANGLE_MIN, ANGLE_MAX, -390], # 14 Right Shoulder Roll
        [ANGLE_MIN, ANGLE_MAX, 250],  # 15 Right Elbow Roll
        [ANGLE_MIN, ANGLE_MAX, 195],  # 16 Right Thigh Roll
        [ANGLE_MIN, ANGLE_MAX, -105], # 17 Right Thigh Pitch
        [ANGLE_MIN, ANGLE_MAX, -510], # 18 Right Knee Pitch
        [ANGLE_MIN, ANGLE_MAX, -305], # 19 Right Foot Pitch
        [ANGLE_MIN, ANGLE_MAX, 60],   # 20 Right Foot Roll
        [ANGLE_MIN, ANGLE_MAX, ANGLE_NEUTRAL], # 21
        [ANGLE_MIN, ANGLE_MAX, ANGLE_NEUTRAL], # 22
        [ANGLE_MIN, ANGLE_MAX, ANGLE_NEUTRAL], # 23
    ]

    def __init__(self):
        # Initialize PCA9685 using local driver
        # Defaulting to 0x60 as per Emakefun driver, but 0x40 is standard.
        # Use 0x60 since user referred to Emakefun repo.
        try:
            self.pca = PCA9685(address=0x60)
            self.pca.setPWMFreq(self.PWM_FREQ)
            logger.info("PCA9685 Initialized at 0x60")
        except Exception as e:
            logger.error(f"Failed to initialize PCA9685 at 0x60: {e}")
            # Fallback check for 0x40?
            try:
                self.pca = PCA9685(address=0x40)
                self.pca.setPWMFreq(self.PWM_FREQ)
                logger.info("PCA9685 Initialized at 0x40")
            except Exception as e2:
                logger.error(f"Failed to initialize PCA9685 at 0x40: {e2}")
                self.pca = None

        self.settings = []
        for s in self.SETTINGS_INITIAL:
            self.settings.append({'min': s[0], 'max': s[1], 'home': s[2]})

        self.load_config()

        # Initialize to home
        for joint_id in range(self.SUM):
            self.set_angle(joint_id, self.settings[joint_id]['home'])

    def load_config(self):
        if os.path.exists(self.CONFIG_FILE):
            try:
                with open(self.CONFIG_FILE, 'r') as f:
                    loaded = json.load(f)
                    for i in range(min(len(loaded), self.SUM)):
                        # Only updating home for now as that's what calibration usually touches
                        if 'home' in loaded[i]:
                            self.settings[i]['home'] = loaded[i]['home']
            except Exception as e:
                logger.error(f"Failed to load config: {e}")

    def save_config(self):
        try:
            with open(self.CONFIG_FILE, 'w') as f:
                json.dump(self.settings, f, indent=4)
            logger.info(f"Config saved to {self.CONFIG_FILE}")
        except Exception as e:
            logger.error(f"Failed to save config: {e}")

    def map_range(self, x, in_min, in_max, out_min, out_max):
        return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min

    def get_pwm_ticks(self, angle):
        # Map angle (-800 to 800) to PWM ticks (175 to 575)
        return int(self.map_range(angle, self.ANGLE_MIN, self.ANGLE_MAX, self.PWM_MIN, self.PWM_MAX))

    def set_angle(self, joint_id, angle):
        if joint_id >= self.SUM:
            return False

        # Constrain
        angle = max(self.settings[joint_id]['min'], min(angle, self.settings[joint_id]['max']))
        
        # Calculate PWM
        ticks = self.get_pwm_ticks(angle)

        # Get Channel
        channel = self.SERVO_MAP.get(joint_id)
        
        if channel is None:
            return False
            
        if channel >= 16:
            # GPIO or unused - ignore as per requirements (exclude arm motors on GPIO)
            return True 

        # Write to PCA
        if self.pca:
            # Local driver uses setPWM(channel, on, off)
            # off value is the ticks (0 to ticks)
            self.pca.setPWM(channel, 0, ticks)
            
        return True


    def set_angle_diff(self, joint_id, angle_diff):
        if joint_id >= self.SUM:
            return False
        
        target = angle_diff + self.settings[joint_id]['home']
        return self.set_angle(joint_id, target)
