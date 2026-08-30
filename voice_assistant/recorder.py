import sounddevice as sd
import scipy.io.wavfile as wav
import numpy as np
import keyboard
from config import SAMPLE_RATE, CHANNELS, TEMP_AUDIO_PATH, HOTKEY


def record_audio_until_release():
    print("Recording... Release key to stop.")

    chunk_size = 1024
    audio_chunks = []

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="int16"
    ) as stream:

        while keyboard.is_pressed(HOTKEY):
            chunk, overflowed = stream.read(chunk_size)
            audio_chunks.append(chunk)

    if len(audio_chunks) == 0:
        return None

    audio = np.concatenate(audio_chunks, axis=0)

    wav.write(TEMP_AUDIO_PATH, SAMPLE_RATE, audio)

    print("Recording complete.")
    return TEMP_AUDIO_PATH