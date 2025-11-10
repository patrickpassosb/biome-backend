import cv2
import sys
import numpy as np
from fastdtw import fastdtw
from scipy.spatial.distance import cosine
import mediapipe as mp
from utils.pose_features import ema
from utils.sound import speak
from utils.joint_angles import extract_angle_vector

IDEAL_RANGES = {
    'hip': (85, 130),   
    'knee': (70, 140),   
    'back': (150, 180),  
    'ankle': (70, 110)   
}

def analyze_pose(angles):
    """Analyze pose angles and return (score, feedback)."""
    if angles is None or len(angles) != 4:
        return 0, "Invalid pose detected"

    hip_angle, knee_angle, back_angle, ankle_angle = angles
    feedback = []
    scores = []

   
    hip_min, hip_max = IDEAL_RANGES['hip']
    if hip_angle < hip_min:
        feedback.append("Hips too high")
        scores.append(hip_angle / hip_min * 100)
    elif hip_angle > hip_max:
        feedback.append("Hips too low")
        scores.append((180 - hip_angle) / (180 - hip_max) * 100)
    else:
        scores.append(100)

   
    knee_min, knee_max = IDEAL_RANGES['knee']
    if knee_angle < knee_min:
        feedback.append("Knees too bent")
        scores.append(knee_angle / knee_min * 100)
    elif knee_angle > knee_max:
        feedback.append("Need to bend knees more")
        scores.append((180 - knee_angle) / (180 - knee_max) * 100)
    else:
        scores.append(100)


    back_min, back_max = IDEAL_RANGES['back']
    if back_angle < back_min:
        feedback.append("Straighten your back")
        scores.append(back_angle / back_min * 100)
    else:
        scores.append(100)

    ankle_min, ankle_max = IDEAL_RANGES['ankle']
    if ankle_angle < ankle_min:
        feedback.append("Ankles too bent")
        scores.append(ankle_angle / ankle_min * 100)
    elif ankle_angle > ankle_max:
        feedback.append("Need more ankle flexion")
        scores.append((180 - ankle_angle) / (180 - ankle_max) * 100)
    else:
        scores.append(100)

   
    weights = np.array([0.35, 0.35, 0.2, 0.1])
    final_score = np.average(scores, weights=weights)

    if not feedback:
        return final_score, "Good form"
    return final_score, " | ".join(feedback)

def load_ref(path: str) -> np.ndarray:
    """Load and validate reference data."""
    try:
        arr = np.load(path, allow_pickle=True)
        print("[DEBUG] Initial load shape:", arr.shape, "dtype:", arr.dtype)
        
        if arr.ndim == 1:
            arr = arr[None, :]
            
        
        if arr.dtype == 'O':
            valid_frames = [frame for frame in arr if frame is not None]
            if not valid_frames:
                raise ValueError("No valid frames found in reference data")
            arr = np.stack(valid_frames)
        
        arr = arr.astype(np.float32, copy=False)
        print("[DEBUG] Value range:", arr.min(), "to", arr.max())
        return arr
        
    except Exception as e:
        print(f"[ERROR] Failed to load reference data: {e}")
        raise

def run_live_match(ref_path, exercise_name="squat", speak_on=True):
    print("[DEBUG] Loading reference from:", ref_path)
    
    try:
        ref = load_ref(ref_path)
        print(f"[INFO] Loaded ref: {ref_path} shape={ref.shape}")
        if len(ref) < 20:
            raise RuntimeError(f"Reference too short or empty: {ref_path}")
    except Exception as e:
        print(f"[ERROR] Failed to load reference: {e}")
        raise
    try:
        mp_pose = mp.solutions.pose
        pose = mp_pose.Pose(
            static_image_mode=False,
            model_complexity=1,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
       
    except Exception as e:
        print(f"[ERROR] Failed to initialize MediaPipe: {e}")
        raise

    try:
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)  # Try DirectShow first
        if not cap.isOpened():
            cap = cv2.VideoCapture(0)  # Fallback to default
        if not cap.isOpened():
            raise RuntimeError("Could not open camera - please check if it's connected and not in use")
        
        # Try to set reasonable camera parameters
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        cap.set(cv2.CAP_PROP_FPS, 30)
        
        
        print(f"[DEBUG] Camera resolution: {int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}")
    except Exception as e:
        print(f"[ERROR] Camera initialization failed: {e}")
        raise

    smoothed = None
    last_feedback = ""
    feedback_cooldown = 0
    
    EXCELLENT_THRESHOLD = 90.0
    GOOD_THRESHOLD = 75.0
    OKAY_THRESHOLD = 60.0
    FEEDBACK_COOLDOWN = 30  

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("[ERROR] Failed to read from camera")
                break

            h, w = frame.shape[:2]
            if h > w:
                frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
            frame = cv2.resize(frame, (960, 540))

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = pose.process(rgb)

            score = 0.0
            feedback = "NO BODY DETECTED"
            color = (128, 128, 128) 

            if results.pose_landmarks:
                
                curr_angles = extract_angle_vector(results.pose_landmarks.landmark)
                if curr_angles is not None:
                    smoothed = ema(smoothed, curr_angles, 0.2)
                    if smoothed is not None:
                        score, pose_feedback = analyze_pose(smoothed)
                        
                        if score >= EXCELLENT_THRESHOLD:
                            feedback = "EXCELLENT FORM ⭐"
                            color = (0, 255, 0)  
                        elif score >= GOOD_THRESHOLD:
                            feedback = "GOOD FORM ✅"
                            color = (0, 255, 255)
                        elif score >= OKAY_THRESHOLD:
                            feedback = "OKAY FORM 🔄"
                            color = (0, 165, 255)
                        else:
                            feedback = "FIX FORM ❌"
                            color = (0, 0, 255)  
                            
                        if score < EXCELLENT_THRESHOLD:
                            feedback = f"{feedback}\n{pose_feedback}"

                        if feedback != last_feedback and feedback_cooldown <= 0:
                            if speak_on:
                                try:
                                    speak(pose_feedback if score < EXCELLENT_THRESHOLD else "Perfect form")
                                    feedback_cooldown = FEEDBACK_COOLDOWN
                                except Exception:
                                    pass 
                            last_feedback = feedback

            feedback_cooldown = max(0, feedback_cooldown - 1)

            cv2.putText(frame, f"{exercise_name.upper()} FORM CHECK", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255,255,255), 2)
            cv2.putText(frame, f"Score: {int(score)}%", (10, 70),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.1, color, 3)
            
            y = 110
            for line in feedback.split('\n'):
                cv2.putText(frame, line, (10, y),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (230,230,230), 2)
                y += 40

            if results.pose_landmarks:
                mp.solutions.drawing_utils.draw_landmarks(
                    frame, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)

            cv2.imshow("Form Checker", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    except Exception as e:
        print(f"[ERROR] Runtime error: {e}")
    finally:
        print("[DEBUG] Cleaning up...")
        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    print("in if")
    ref_path = sys.argv[1] if len(sys.argv) > 1 else "refs/ref_squat.npy"
    exercise = sys.argv[2] if len(sys.argv) > 2 else "squat"
    run_live_match(ref_path, exercise)