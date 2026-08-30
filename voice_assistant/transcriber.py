from faster_whisper import WhisperModel
from config import MODEL_SIZE

print("Loading Whisper model...")
model = WhisperModel(MODEL_SIZE, compute_type="int8")
print("Whisper ready.")


def transcribe(audio_path):
    segments, info = model.transcribe(
    audio_path,
    language="en",
    beam_size=1
    )

    text = ""

    for segment in segments:
        text += segment.text + " "

    clean = text.strip()
    # remove problematic unicode
    clean = clean.encode("ascii", errors="ignore").decode()
    return clean