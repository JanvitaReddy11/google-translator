import pyaudio
import wave

# Audio recording parameters
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1024
AUDIO_FILE = "recorded_audio.wav"

def record_audio(duration):
    """Records audio from the microphone and saves it as a .wav file."""
    audio = pyaudio.PyAudio()
    stream = audio.open(format=FORMAT, channels=CHANNELS,
                        rate=RATE, input=True,
                        frames_per_buffer=CHUNK)

    print("🎙️ Recording started... Speak now!")
    frames = []
    
    for _ in range(0, int(RATE / CHUNK * duration)):
        data = stream.read(CHUNK)
        frames.append(data)

    print("✅ Recording complete!")

    stream.stop_stream()
    stream.close()
    audio.terminate()

    # Save the recorded audio as a .wav file
    with wave.open(AUDIO_FILE, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(audio.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b"".join(frames))

    return AUDIO_FILE
