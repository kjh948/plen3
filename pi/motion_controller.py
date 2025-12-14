import json
import time
import logging
from joint_controller import JointController

logger = logging.getLogger(__name__)

class MotionController:
    # Map device names to Joint IDs
    # Based on JointController.cpp comments
    DEVICE_MAP = {
        "left_shoulder_pitch": 0,
        "left_thigh_yaw": 1,
        "left_shoulder_roll": 2,
        "left_elbow_roll": 3,
        "left_thigh_roll": 4,
        "left_thigh_pitch": 5,
        "left_knee_pitch": 6,
        "left_foot_pitch": 7,
        "left_foot_roll": 8,
        
        "right_shoulder_pitch": 12,
        "right_thigh_yaw": 13,
        "right_shoulder_roll": 14,
        "right_elbow_roll": 15,
        "right_thigh_roll": 16,
        "right_thigh_pitch": 17,
        "right_knee_pitch": 18,
        "right_foot_pitch": 19,
        "right_foot_roll": 20
    }

    UPDATE_INTERVAL_MS = 40  # 40ms from Firmware

    def __init__(self, joint_controller):
        self.joint_ctrl = joint_controller
        self.playing = False
        self.stop_flag = False

    def load_motion(self, file_path):
        with open(file_path, 'r') as f:
            data = json.load(f)
        return data

    def play(self, file_path, speed=1.0):
        """
        Plays a motion file.
        This blocking function runs the loop.
        To make it non-blocking, we'd need a separate thread or async.
        For simplicity, implementing blocking for this script.
        """
        self.playing = True
        self.stop_flag = False
        
        try:
            motion_data = self.load_motion(file_path)
            frames = motion_data.get('frames', [])
            
            logger.info(f"Playing motion: {motion_data.get('name', 'Unknown')} with {len(frames)} frames at {speed}x speed")

            # Reset logic if needed? Usually motions start from current position.
            # We need to interpolate from CURRENT position to FIRST frame?
            # Or assume First Frame is reached instantly?
            # Firmware: m_setupFrame(0) loads next frame (0) and diffs with current.
            # So yes, it interpolates from current.

            current_angles = [0] * self.joint_ctrl.SUM
            # Should get current angles from JointController?
            # JointController doesn't store 'current angle' except in PWM setting.
            # But we can track it (simulation).
            # Actually, MotionController in FW tracks 'm_current_fixed_points'.
            
            # We need to read "current" state.
            # Since we can't read from servos, we assume we are at the last set position.
            # We will maintain a state in JointController or here.
            # Let's initialize 'current_angles' to 0 (HOME implicitly) or track them.
            # Ideally JointController should have 'get_angle(id)'.
            
            # For this script, lets assume start at 0 (Home).
            # Or better, we should initialize logical angles to HOME of each joint.
            # But deviation is 0 at HOME?
            # Yes, values in JSON are deviation.
            # So current deviation starts at 0.
            
            current_deviations = [0.0] * self.joint_ctrl.SUM

            for frame_idx, frame in enumerate(frames):
                if self.stop_flag:
                    break
                
                # Apply speed factor (higher speed means lower transition time)
                transition_time = frame.get('transition_time_ms', 200)
                if speed > 0:
                    transition_time /= speed
                

                outputs = frame.get('outputs', [])
                
                # Build target deviations for this frame
                target_deviations = current_deviations[:] # Start with current
                
                # Update targets based on frame outputs
                for out in outputs:
                    device = out.get('device')
                    val = out.get('value')
                    joint_id = self.DEVICE_MAP.get(device)
                    
                    if joint_id is not None:
                        target_deviations[joint_id] = float(val)

                # Interpolation
                steps = max(1, int(transition_time / self.UPDATE_INTERVAL_MS))
                
                diffs = []
                for i in range(self.joint_ctrl.SUM):
                    diff = (target_deviations[i] - current_deviations[i]) / steps
                    diffs.append(diff)
                
                # Run steps
                for step in range(steps):
                    start_time = time.time()
                    
                    for i in range(self.joint_ctrl.SUM):
                        current_deviations[i] += diffs[i]
                        # Set angle (deviation + home)
                        # We use set_angle_diff logic which adds Home
                        self.joint_ctrl.set_angle_diff(i, int(current_deviations[i]))
                    
                    # Sleep remainder of 40ms
                    elapsed = (time.time() - start_time) * 1000
                    sleep_time = (self.UPDATE_INTERVAL_MS - elapsed) / 1000.0
                    if sleep_time > 0:
                        time.sleep(sleep_time)

                # Ensure we hit exact targets at end of frame
                for i in range(self.joint_ctrl.SUM):
                    current_deviations[i] = target_deviations[i]
                    self.joint_ctrl.set_angle_diff(i, int(current_deviations[i]))

        except Exception as e:
            logger.error(f"Error playing motion: {e}")
        finally:
            self.playing = False

    def stop(self):
        self.stop_flag = True

