
import os
import logging
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GNANI_API_KEY")
STT_URL = "https://api.vachana.ai/stt/v3"
LOGGER = logging.getLogger(__name__)


def transcribe_audio(audio_path, language="te-IN", *, model="prisma-v3.0",
                     output_format="transcribe", return_metadata=False):

    if not API_KEY:
        raise ValueError("Gnani API key missing in .env")

    if not os.path.exists(audio_path):
        raise FileNotFoundError(audio_path)

    headers = {
        "X-API-Key-ID": API_KEY
    }

    data = {
        "language_code": language,
        "model": model,
        "format": output_format,
    }

    with open(audio_path, "rb") as audio:
        files = {
            "audio_file": (
                os.path.basename(audio_path),
                audio,
                "audio/wav"
            )
        }

        response = requests.post(
            STT_URL,
            headers=headers,
            data=data,
            files=files,
            timeout=60
        )

    LOGGER.info("Gnani STT response status=%s", response.status_code)
    response.raise_for_status()

    result = response.json()
    LOGGER.info("Gnani STT result model=%s detected_language=%s",
                result.get("model"), result.get("detected_language_code"))

    if not result.get("success"):
        raise RuntimeError(f"STT failed: {result}")

    transcription = {
        "transcript": result.get("transcript", ""),
        "model": result.get("model"),
        "detected_language": result.get("detected_language_code"),
        "requested_language": language,
        "format": output_format,
    }
    return transcription if return_metadata else transcription["transcript"]
