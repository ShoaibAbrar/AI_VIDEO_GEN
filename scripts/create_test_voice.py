import math
import os
from pathlib import Path
import struct
import wave

output_path = Path("materials/test_reference_voice.wav")
output_path.parent.mkdir(parents=True, exist_ok=True)

sample_rate = 24000
duration_s = 5.0
num_samples = int(sample_rate * duration_s)
base_freq = 150.0  # Warm natural vocal fundamental

with wave.open(str(output_path), "wb") as wf:
    wf.setnchannels(1)  # Mono
    wf.setsampwidth(2)  # 16-bit
    wf.setframerate(sample_rate)

    frames = bytearray()
    for i in range(num_samples):
        t = i / sample_rate
        # Natural speech cadence envelope
        envelope = 0.7 + 0.3 * math.sin(2 * math.pi * 2.5 * t)
        f0 = base_freq + 12.0 * math.sin(2 * math.pi * 1.5 * t)
        v1 = math.sin(2 * math.pi * f0 * t)
        v2 = 0.5 * math.sin(2 * math.pi * f0 * 2.0 * t)
        v3 = 0.25 * math.sin(2 * math.pi * f0 * 3.0 * t)
        sample_val = int(9000 * envelope * (v1 + v2 + v3))
        sample_val = max(-32768, min(32767, sample_val))
        frames.extend(struct.pack("<h", sample_val))

    wf.writeframes(frames)

print(f"Created authorized reference test voice asset: {output_path} ({duration_s}s, {sample_rate}Hz)")
