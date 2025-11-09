import numpy as np
from utils.pose_features import angle

def extract_angle_vector(landmarks):
    
    if landmarks is None:
        return None

    def get(idx):
        try:
            return np.array([landmarks[idx].x, landmarks[idx].y, landmarks[idx].z])
        except (IndexError, AttributeError):
            return None
    right_shoulder = get(12)
    left_hip = get(23)
    right_hip = get(24)
    left_knee = get(25)
    right_knee = get(26)
    left_ankle = get(27)
    right_ankle = get(28)
    right_foot = get(30)

    key_points = [right_shoulder, left_hip, right_hip, left_knee, right_knee, left_ankle, right_ankle, right_foot]
    if any(p is None for p in key_points):
        return None

    try:
        hip_angle = angle(right_shoulder, right_hip, right_knee) 
        knee_angle = angle(right_hip, right_knee, right_ankle)   
        back_angle = angle(right_shoulder, right_hip, right_knee)
        ankle_angle = angle(right_knee, right_ankle, right_foot) 

        angles = np.array([hip_angle, knee_angle, back_angle, ankle_angle], dtype=np.float32)
        
        if np.any(angles < 0) or np.any(angles > 180):
            return None
            
        return angles

    except Exception:
        return None
