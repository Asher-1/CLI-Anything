"""Registry of ACloudViewer AICore plugin batch commands.

Only stable command identity and input shape live here. The binary remains the
source of truth for options: ``ai schema`` asks each command for its HELP JSON.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class AICommand:
    name: str
    command: str
    summary: str
    input_shape: str = "images"


_COMMANDS = (
    AICommand("rmbg", "RMBG_REMOVE", "Foreground extraction / background removal"),
    AICommand("deeplsd", "DEEPLSD_LINES", "Line and wireframe extraction"),
    AICommand("rfdetr", "RFDETR_DETECT", "RF-DETR detection and instance segmentation"),
    AICommand("yolo", "YOLO_PREDICT", "YOLO detect/segment/pose/OBB/classify/depth"),
    AICommand("yolo-track", "YOLO_TRACK", "YOLO multi-object tracking", "video-or-frames"),
    AICommand("da3", "DA3_DEPTH", "Depth Anything 3 depth and reconstruction", "images-or-sets"),
    AICommand("face", "FACE_DETECT", "Face detection, landmarks, analysis and verification"),
    AICommand("gkd", "GKD_KEYPOINTS", "General keypoint detection"),
    AICommand("ocr", "OCR_RECOGNIZE", "OCR text, layout and table (HTML/CSV) recognition"),
    AICommand("sam3", "SAM3_SEGMENT", "SAM3/SAM2 promptable segmentation"),
    AICommand("lightglue", "LIGHTGLUE_MATCH", "SIFT/ALIKED + LightGlue image matching", "image-pairs"),
    AICommand("freesplatter", "FREESPLATTER_RECONSTRUCT", "Multiview 3D Gaussian reconstruction", "image-sets"),
    AICommand("trellis", "TRELLIS_GENERATE", "TRELLIS image-to-3D mesh/GLB generation"),
    AICommand("lingbot-map", "LINGBOT_MAP_RECONSTRUCT", "LingBot RGB sequence/video mapping", "sequence-or-video"),
    AICommand("anylabel", "ANYLABEL_INFER", "qAnyLabeling generic auto-annotation"),
    AICommand("llm", "LLM_GENERATE", "Local LLM/VLM text generation", "text-or-images"),
    AICommand("map-anything", "MAP_ANYTHING_RECONSTRUCT", "MapAnything multiview reconstruction", "image-sets"),
    AICommand("sam3d", "SAM3D_GENERATE", "SAM3D image-to-3D generation"),
    AICommand("openpcdet", "OPENPCDET_DETECT", "OpenPCDet LiDAR point cloud 3D object detection", "point-clouds"),
)

_BY_NAME = {item.name: item for item in _COMMANDS}
_BY_COMMAND = {item.command: item for item in _COMMANDS}


def list_ai_commands() -> list[dict]:
    return [asdict(item) for item in _COMMANDS]


def resolve_ai_command(value: str) -> AICommand:
    key = value.strip()
    item = _BY_NAME.get(key.lower()) or _BY_COMMAND.get(key.lstrip("-").upper())
    if item is None:
        valid = ", ".join(command.name for command in _COMMANDS)
        raise ValueError(f"Unknown AI task '{value}'. Available: {valid}")
    return item
