
import subprocess
import imageio_ffmpeg
import os

ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

input_file = "sample.wav"
output_file = "sample_pcm.wav"

if not os.path.exists(input_file):
    raise FileNotFoundError("sample.wav not found!")

command = [
    ffmpeg,
    "-y",
    "-i", input_file,
    "-ac", "1",
    "-ar", "16000",
    "-c:a", "pcm_s16le",
    output_file
]

subprocess.run(command, check=True)

print("\nAudio conversion successful!")
print("Output:", output_file)
