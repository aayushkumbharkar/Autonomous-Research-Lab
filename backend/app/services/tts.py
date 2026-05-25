"""
TTS Service (pluggable).

Provides text-to-speech capability. Uses pyttsx3 for offline.
Can be extended with cloud providers.
"""

from typing import Optional
from app.utils.logging import get_logger

logger = get_logger(__name__)


def text_to_speech(text: str, output_path: Optional[str] = None) -> Optional[str]:
    """
    Convert text to speech.

    Args:
        text: Text to convert
        output_path: Optional path to save audio file

    Returns:
        Path to audio file, or None if played directly
    """
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.setProperty('rate', 150)

        if output_path:
            engine.save_to_file(text, output_path)
            engine.runAndWait()
            return output_path
        else:
            engine.say(text)
            engine.runAndWait()
            return None
    except Exception as e:
        logger.warning("tts_failed", error=str(e))
        return None
