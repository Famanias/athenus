import os
from typing import List

class FrameExtractor:
    """Extracts visual keyframes from video files for slide OCR & visual RAG."""
    
    async def extract_keyframes(self, video_path: str, output_dir: str, interval_seconds: int = 30) -> List[str]:
        os.makedirs(output_dir, exist_ok=True)
        # Mock keyframe extraction paths for test environment
        sample_frame = os.path.join(output_dir, "frame_0001.jpg")
        with open(sample_frame, "wb") as f:
            f.write(b"MOCK_FRAME_IMAGE_DATA")
        return [sample_frame]
