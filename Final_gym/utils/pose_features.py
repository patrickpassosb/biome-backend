import numpy as np

KEYS = [
    11, 12,  
    13, 14,  
    15, 16,  
    23, 24,  
    25, 26,  
    27, 28,  
]

def _center_and_scale(points33):
    """
    points33: (33,3) np.array in normalized coords
    Center on mid-hip, scale by shoulder-width to be size-invariant.
    """
    pts = points33.copy()
    mid_hip = (pts[23, :2] + pts[24, :2]) / 2.0
    shoulder_width = np.linalg.norm(pts[11, :2] - pts[12, :2]) + 1e-6

    pts[:, 0] = (pts[:, 0] - mid_hip[0]) / shoulder_width
    pts[:, 1] = (pts[:, 1] - mid_hip[1]) / shoulder_width
    pts[:, 2] = pts[:, 2] / shoulder_width
    return pts

def vectorize(points33):
    """
    Return a 1-D feature vector (only selected joints, centered & scaled).
    """
    norm = _center_and_scale(points33)
    sel = norm[KEYS, :]
    return sel.reshape(-1)

def ema(prev, curr, alpha=0.2):
    if prev is None:
        return curr
    return alpha * curr + (1 - alpha) * prev


def angle(a, b, c):
    
    ba = a - b
    bc = c - b
    ba /= (np.linalg.norm(ba) + 1e-8)
    bc /= (np.linalg.norm(bc) + 1e-8)
    cosine_angle = np.clip(np.dot(ba, bc), -1.0, 1.0)
    return np.degrees(np.arccos(cosine_angle))
