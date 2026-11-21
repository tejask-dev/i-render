"""Labelled example RobotSpecs (spec 03b) for the three sample sketches.

Millimetres, Z up, origin on the ground under the robot, +X = robot's right,
+Y = front, pos_mm = centre of the part's bounding box. Each example is drawn
for the default 20 cm desktop brief and every part overlaps its attach_to
parent by 2 mm, so cad.export_model leaves them untouched at that size.
"""

TEMPLATE_LABELS = {
    "wheelbot": "Wheel bot",
    "armbot": "Arm bot",
    "blobbot": "Blob bot",
}

WHEELBOT = {
    "robot_name": "Rollo",
    "parts": [
        {"id": "body", "label": "Body", "primitive": "rounded_box",
         "dims_mm": [100, 90, 80], "pos_mm": [0, 0, 58], "rot_deg": [0, 0, 0],
         "attach_to": None, "category": "structure", "function": "hold everything"},
        {"id": "head", "label": "Head", "primitive": "rounded_box",
         "dims_mm": [80, 70, 60], "pos_mm": [0, 0, 126], "rot_deg": [0, 0, 0],
         "attach_to": "body", "category": "structure", "function": "look cute"},
        {"id": "eye_left", "label": "Left eye", "primitive": "cylinder",
         "dims_mm": [16, 6], "pos_mm": [-18, 36, 130], "rot_deg": [90, 0, 0],
         "attach_to": "head", "category": "light", "function": "glow"},
        {"id": "eye_right", "label": "Right eye", "primitive": "cylinder",
         "dims_mm": [16, 6], "pos_mm": [18, 36, 130], "rot_deg": [90, 0, 0],
         "attach_to": "head", "category": "light", "function": "glow"},
        {"id": "antenna", "label": "Antenna", "primitive": "antenna",
         "dims_mm": [40], "pos_mm": [0, 0, 175.5], "rot_deg": [0, 0, 0],
         "attach_to": "head", "category": "decor", "function": "look cute"},
        {"id": "mount_left", "label": "Left motor mount", "primitive": "motor_mount",
         "dims_mm": [24], "pos_mm": [-55.5, 0, 30.5], "rot_deg": [0, 0, 0],
         "attach_to": "body", "category": "motion", "function": "drive"},
        {"id": "mount_right", "label": "Right motor mount", "primitive": "motor_mount",
         "dims_mm": [24], "pos_mm": [55.5, 0, 30.5], "rot_deg": [0, 0, 0],
         "attach_to": "body", "category": "motion", "function": "drive"},
        {"id": "wheel_left", "label": "Left wheel", "primitive": "wheel",
         "dims_mm": [70, 22], "pos_mm": [-72, 0, 35], "rot_deg": [0, 0, 0],
         "attach_to": "mount_left", "category": "motion", "function": "drive"},
        {"id": "wheel_right", "label": "Right wheel", "primitive": "wheel",
         "dims_mm": [70, 22], "pos_mm": [72, 0, 35], "rot_deg": [0, 0, 0],
         "attach_to": "mount_right", "category": "motion", "function": "drive"},
        {"id": "caster", "label": "Rear caster", "primitive": "sphere",
         "dims_mm": [20], "pos_mm": [0, -32, 10], "rot_deg": [0, 0, 0],
         "attach_to": "body", "category": "motion", "function": "balance"},
    ],
    "functions": [
        {"name": "drive", "parts": ["wheel_left", "wheel_right", "mount_left", "mount_right"]},
        {"name": "light_up", "parts": ["eye_left", "eye_right"]},
    ],
    "assumptions": [
        "Labelled example, not read from a photo.",
        "Two TT gear motors drive the wheels; a rear ball caster keeps it level.",
        "Sized for a 20 cm desktop robot.",
    ],
    "confidence": 1.0,
}

ARMBOT = {
    "robot_name": "Grabby",
    "parts": [
        {"id": "base", "label": "Base", "primitive": "box",
         "dims_mm": [110, 110, 30], "pos_mm": [0, 0, 15], "rot_deg": [0, 0, 0],
         "attach_to": None, "category": "structure", "function": "stay steady"},
        {"id": "turntable", "label": "Turntable", "primitive": "cylinder",
         "dims_mm": [80, 14], "pos_mm": [0, 0, 35], "rot_deg": [0, 0, 0],
         "attach_to": "base", "category": "motion", "function": "spin"},
        {"id": "shoulder_servo", "label": "Shoulder servo mount", "primitive": "servo_mount",
         "dims_mm": [], "pos_mm": [0, 0, 51], "rot_deg": [0, 0, 0],
         "attach_to": "turntable", "category": "motion", "function": "lift the arm"},
        {"id": "upper_arm", "label": "Upper arm", "primitive": "arm_link",
         "dims_mm": [130, 22, 8], "pos_mm": [0, 8.25, 110], "rot_deg": [90, -90, 0],
         "attach_to": "shoulder_servo", "category": "structure", "function": "reach"},
        {"id": "elbow_servo", "label": "Elbow servo mount", "primitive": "servo_mount",
         "dims_mm": [], "pos_mm": [0, 0, 166], "rot_deg": [0, 0, 0],
         "attach_to": "upper_arm", "category": "motion", "function": "bend the arm"},
        {"id": "forearm", "label": "Forearm", "primitive": "arm_link",
         "dims_mm": [90, 20, 8], "pos_mm": [35, -8.25, 166], "rot_deg": [90, 0, 0],
         "attach_to": "elbow_servo", "category": "structure", "function": "reach"},
        {"id": "wrist", "label": "Wrist", "primitive": "box",
         "dims_mm": [12, 24, 30], "pos_mm": [84, -8.25, 166], "rot_deg": [0, 0, 0],
         "attach_to": "forearm", "category": "structure", "function": "hold the fingers"},
        {"id": "finger_top", "label": "Top finger", "primitive": "cone",
         "dims_mm": [10, 4, 34], "pos_mm": [105, -8.25, 175], "rot_deg": [0, 90, 0],
         "attach_to": "wrist", "category": "motion", "function": "grab"},
        {"id": "finger_bottom", "label": "Bottom finger", "primitive": "cone",
         "dims_mm": [10, 4, 34], "pos_mm": [105, -8.25, 157], "rot_deg": [0, 90, 0],
         "attach_to": "wrist", "category": "motion", "function": "grab"},
    ],
    "functions": [
        {"name": "grab", "parts": ["finger_top", "finger_bottom", "wrist", "forearm", "elbow_servo"]},
        {"name": "spin", "parts": ["turntable", "shoulder_servo"]},
    ],
    "assumptions": [
        "Labelled example, not read from a photo.",
        "Two SG90 micro servos move the shoulder and elbow.",
        "Sized for a 20 cm desktop robot.",
    ],
    "confidence": 1.0,
}

BLOBBOT = {
    "robot_name": "Glowb",
    "parts": [
        {"id": "body", "label": "Blob body", "primitive": "sphere",
         "dims_mm": [150], "pos_mm": [0, 0, 80], "rot_deg": [0, 0, 0],
         "attach_to": None, "category": "structure", "function": "be huggable"},
        {"id": "foot_left", "label": "Left foot", "primitive": "rounded_box",
         "dims_mm": [40, 50, 16], "pos_mm": [-35, 5, 8], "rot_deg": [0, 0, 0],
         "attach_to": "body", "category": "structure", "function": "stand"},
        {"id": "foot_right", "label": "Right foot", "primitive": "rounded_box",
         "dims_mm": [40, 50, 16], "pos_mm": [35, 5, 8], "rot_deg": [0, 0, 0],
         "attach_to": "body", "category": "structure", "function": "stand"},
        {"id": "belly_light", "label": "Belly light", "primitive": "sphere",
         "dims_mm": [60], "pos_mm": [0, 52, 70], "rot_deg": [0, 0, 0],
         "attach_to": "body", "category": "light", "function": "glow"},
        {"id": "eye_left", "label": "Left eye", "primitive": "sphere",
         "dims_mm": [16], "pos_mm": [-22, 58, 112], "rot_deg": [0, 0, 0],
         "attach_to": "body", "category": "decor", "function": "look cute"},
        {"id": "eye_right", "label": "Right eye", "primitive": "sphere",
         "dims_mm": [16], "pos_mm": [22, 58, 112], "rot_deg": [0, 0, 0],
         "attach_to": "body", "category": "decor", "function": "look cute"},
        {"id": "hat", "label": "Party hat", "primitive": "cone",
         "dims_mm": [50, 6, 50], "pos_mm": [0, 0, 173], "rot_deg": [0, 0, 0],
         "attach_to": "body", "category": "decor", "function": "look cute"},
    ],
    "functions": [
        {"name": "light_up", "parts": ["belly_light"]},
    ],
    "assumptions": [
        "Labelled example, not read from a photo.",
        "The belly dome is a diffuser for one LED.",
        "Sized for a 20 cm desktop robot.",
    ],
    "confidence": 1.0,
}

TEMPLATES = {
    "wheelbot": WHEELBOT,
    "armbot": ARMBOT,
    "blobbot": BLOBBOT,
}
