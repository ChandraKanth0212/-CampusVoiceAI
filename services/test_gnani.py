
import os

from services.gnani_tts import generate_speech
from services.gnani_stt import transcribe_audio


print("\n================================")
print(" CAMPUSVOICE AI - GNANI API TEST")
print("================================\n")


# TEST 1: TEXT TO SPEECH
print("[1] Testing Gnani Timbre V3.0...")

try:
    text = "నమస్కారం! క్యాంపస్ వాయిస్ ఏఐ కి స్వాగతం."

    output = generate_speech(
        text,
        output_path="response.wav"
    )

    if os.path.exists(output) and os.path.getsize(output) > 100:
        print("SUCCESS: TTS API is working!")
        print("Audio saved:", output)
        print("File size:", os.path.getsize(output), "bytes")
    else:
        print("FAILED: Audio file was not generated.")

except Exception as e:
    print("TTS ERROR:", str(e))


# TEST 2: SPEECH TO TEXT
print("\n[2] Testing Gnani Prisma V3.0...")

audio_path = "sample_pcm.wav"

if not os.path.exists(audio_path):
    print("SKIPPED: sample.wav not found.")
    print("Record a short Telugu voice sample and save it as sample.wav.")
else:
    try:
        transcript = transcribe_audio(
            audio_path,
            language="te-IN"
        )

        print("SUCCESS: STT API is working!")
        print("Recognized text:", transcript)

    except Exception as e:
        print("STT ERROR:", str(e))


print("\n================================")
print(" API TEST COMPLETED")
print("================================")
