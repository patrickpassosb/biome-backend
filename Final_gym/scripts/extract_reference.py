import os
import sys
# For Root Directory
sys.path.append(os.path.dirname(os.path.dirname(__file__)))


try:
    import cv2
    import numpy as np
    import mediapipe as mp
    from utils.pose_features import vectorize, ema
    from utils.joint_angles import extract_angle_vector
    #For Exceptions
except Exception as e:
    print("❌ Import Error:", e)
    sys.exit(1)

def extract_reference(video_path, save_path, max_frames=120):
    mp_pose = mp.solutions.pose
    pose = mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"❌ Cannot open video: {video_path}")
        return

    seq = []
    smoothed = None
    frame_i = 0

    while True:
        ret, frame = cap.read()
        if not ret or frame_i > max_frames:
            break
        h, w = frame.shape[:2]
        if h > w:
            frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)

        frame = cv2.resize(frame, (960, 540))

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        res = pose.process(rgb)

        if res.pose_landmarks:
         
            feat = extract_angle_vector(res.pose_landmarks.landmark)
            if feat is not None and not np.any(np.isnan(feat)):
                smoothed = ema(smoothed, feat, 0.2)
                if smoothed is not None:
                    seq.append(feat)  
        frame_i += 1
        print(f"Processing frame {frame_i}", end="\r")

    cap.release()

    if len(seq) < 20:
        print("⚠️ Not enough pose frames. Try a clearer slow squat video.")
        return

    np.save(save_path, np.stack(seq))
    print(f"\n✅ Saved REFERENCE MODEL: {save_path} ({len(seq)} frames)")

if __name__ == "__main__":
    print("\n=== Reference Pose Extractor ===")
    if len(sys.argv) < 3:
        print("Usage: python scripts/extract_reference.py refs/ref_squat.mp4 refs/ref_squat.npy")
        sys.exit(0)

    extract_reference(sys.argv[1], sys.argv[2])
