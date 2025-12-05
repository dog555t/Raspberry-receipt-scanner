import os
import subprocess
from typing import Optional

LIBCAMERA_CMD = "libcamera-still"


def capture_receipt(output_path: str, timeout: int = 10, resolution: Optional[str] = "1536x864") -> None:
    """Capture a still image using libcamera-still.

    Falls back to creating a blank file if libcamera is unavailable so
    development on non-Pi hosts still works.
    """

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    cmd = [
        LIBCAMERA_CMD,
        "-o",
        output_path,
        "--timeout",
        str(timeout * 1000),
    ]
    if resolution:
        cmd.extend(["--width", resolution.split("x")[0], "--height", resolution.split("x")[1]])

    try:
        subprocess.run(cmd, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        # Development fallback: create an empty placeholder so later steps don't break
        open(output_path, "wb").close()
