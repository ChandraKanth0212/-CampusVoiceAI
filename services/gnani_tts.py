
import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GNANI_API_KEY")

TTS_URL = "https://api.vachana.ai/api/v1/tts/inference"


def generate_speech(text, output_path="response.wav", language="te-IN"):
    if not API_KEY:
        raise ValueError("Gnani API key is missing in .env")

    payload = {
        "text": text,
        "model": "timbre-v3.0",
        "voice": "Lakshmi",
        "language": language,
        "speed": 1.0,
        "audio_config": {
            "encoding": "linear_pcm",
            "container": "wav",
            "num_channels": 1,
            "sample_rate": 48000,
            "sample_width": 2
        }
    }

    headers = {
        "X-API-Key-ID": API_KEY,
        "Content-Type": "application/json"
    }

    response = requests.post(
        TTS_URL,
        headers=headers,
        json=payload,
        timeout=60
    )

    response.raise_for_status()

    with open(output_path, "wb") as audio:
        audio.write(response.content)

    return output_path
