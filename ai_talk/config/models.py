from enum import Enum

class ModelRole(Enum):
    FAST = "fast"
    SMART = "smart"
    BASE = "base"
    CUSTOM = "custom"

MODEL_REGISTRY = {
    ModelRole.FAST: "qwen2.5:3b",
    ModelRole.SMART: "qwen2.5:7b",
    ModelRole.BASE: "qwen2.5:3b",
    ModelRole.CUSTOM: "custom"
}
