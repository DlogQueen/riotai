"""
VOICE & VISION ENGINE
STT, TTS, and Vision for Coach Bear AI
All deps are optional - graceful fallback if not installed
"""

import base64
from pathlib import Path
from openai import OpenAI

# Optional: pyaudio for mic recording
try:
    import pyaudio
    import wave
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False

# Optional: opencv for camera
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False


class VoiceEngine:
    """Speech-to-Text and Text-to-Speech"""

    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)
        self.is_recording = False
        print("🎤 [VOICE] Voice engine ready")

    def speech_to_text(self, audio_file_path: str) -> str:
        """Convert speech to text using Whisper"""
        try:
            with open(audio_file_path, 'rb') as audio_file:
                transcript = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="en"
                )
            return transcript.text
        except Exception as e:
            print(f"❌ [STT] Error: {e}")
            return ""

    def text_to_speech(self, text: str, voice: str = "onyx", output_path: str = None) -> str:
        """Convert text to speech - returns audio bytes path"""
        try:
            import tempfile
            if output_path is None:
                tmp = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
                output_path = tmp.name
                tmp.close()

            response = self.client.audio.speech.create(
                model="tts-1",
                voice=voice,
                input=text
            )
            response.stream_to_file(output_path)
            print(f"🔊 [TTS] Generated: {output_path}")
            return output_path
        except Exception as e:
            print(f"❌ [TTS] Error: {e}")
            return ""

    def record_audio(self, duration: int = 5, output_path: str = "recording.wav") -> str:
        """Record audio from microphone - requires pyaudio"""
        if not PYAUDIO_AVAILABLE:
            print("❌ [RECORDING] pyaudio not installed")
            return ""
        try:
            CHUNK = 1024
            FORMAT = pyaudio.paInt16
            CHANNELS = 1
            RATE = 16000

            p = pyaudio.PyAudio()
            stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE,
                            input=True, frames_per_buffer=CHUNK)

            print(f"🎤 [RECORDING] Recording for {duration} seconds...")
            frames = []
            for _ in range(0, int(RATE / CHUNK * duration)):
                data = stream.read(CHUNK)
                frames.append(data)

            stream.stop_stream()
            stream.close()
            p.terminate()

            wf = wave.open(output_path, 'wb')
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(p.get_sample_size(FORMAT))
            wf.setframerate(RATE)
            wf.writeframes(b''.join(frames))
            wf.close()

            return output_path
        except Exception as e:
            print(f"❌ [RECORDING] Error: {e}")
            return ""


class VisionEngine:
    """Vision capabilities - image analysis and camera"""

    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)
        self.camera = None
        print("👁️ [VISION] Vision engine ready")

    def analyze_image(self, image_path: str, prompt: str = "What's in this image?") -> str:
        """Analyze image using GPT-4o Vision"""
        try:
            with open(image_path, 'rb') as image_file:
                image_data = base64.b64encode(image_file.read()).decode('utf-8')

            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}}
                    ]
                }],
                max_tokens=500
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"❌ [VISION] Error: {e}")
            return ""

    def start_camera(self, camera_index: int = 0) -> bool:
        """Start camera - requires opencv"""
        if not CV2_AVAILABLE:
            print("❌ [CAMERA] opencv not installed")
            return False
        try:
            self.camera = cv2.VideoCapture(camera_index)
            return self.camera.isOpened()
        except Exception as e:
            print(f"❌ [CAMERA] Error: {e}")
            return False

    def capture_frame(self, save_path: str = "frame.jpg") -> str:
        """Capture frame from camera"""
        if not CV2_AVAILABLE:
            return ""
        try:
            if not self.camera or not self.camera.isOpened():
                self.start_camera()
            ret, frame = self.camera.read()
            if ret:
                cv2.imwrite(save_path, frame)
                return save_path
            return ""
        except Exception as e:
            print(f"❌ [CAMERA] Error: {e}")
            return ""

    def stop_camera(self):
        if self.camera and CV2_AVAILABLE:
            self.camera.release()
