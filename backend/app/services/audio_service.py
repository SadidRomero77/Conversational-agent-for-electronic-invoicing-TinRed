"""
Servicio de transcripción de audio.
"""
import subprocess
import tempfile
import os
import base64
import logging
import re

logger = logging.getLogger(__name__)


class AudioTranscriptionError(Exception):
    pass


FFMPEG_PATHS = [
    "ffmpeg",
    r"C:\ffmpeg\ffmpeg-6.1.1-full_build\bin\ffmpeg.exe",
    r"C:\ffmpeg\bin\ffmpeg.exe",
]


def _get_ffmpeg_path() -> str:
    for path in FFMPEG_PATHS:
        try:
            result = subprocess.run([path, "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
            if result.returncode == 0:
                return path
        except:
            continue
    raise AudioTranscriptionError("ffmpeg no encontrado")


def _post_process_numbers(text: str) -> str:
    result = text
    
    word_to_digit = {
        'cero': '0', 'uno': '1', 'una': '1', 'dos': '2', 'tres': '3',
        'cuatro': '4', 'cinco': '5', 'seis': '6', 'siete': '7',
        'ocho': '8', 'nueve': '9'
    }
    
    for word, digit in word_to_digit.items():
        result = re.sub(rf'\b{word}\b', digit, result, flags=re.IGNORECASE)
    
    def join_digits(m):
        return m.group(0).replace(' ', '')
    
    result = re.sub(r'\b(\d(?:\s+\d){3,})\b', join_digits, result)
    result = re.sub(r'(\d{4,})\s+(\d{1,4})\b', r'\1\2', result)
    
    return result.strip()


def transcribe_audio(file_base64: str, mime_type: str = "audio/ogg") -> str:
    import speech_recognition as sr
    
    if not file_base64:
        raise AudioTranscriptionError("No se recibió audio")
    
    try:
        audio_bytes = base64.b64decode(file_base64)
    except:
        raise AudioTranscriptionError("Audio corrupto")
    
    ffmpeg_path = _get_ffmpeg_path()
    
    mime_clean = mime_type.lower().split(';')[0].strip()
    ext = {
        "audio/ogg": ".ogg", "audio/opus": ".ogg", "audio/webm": ".webm",
        "audio/mpeg": ".mp3", "audio/mp3": ".mp3", "audio/m4a": ".m4a"
    }.get(mime_clean, ".ogg")
    
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
        f.write(audio_bytes)
        input_path = f.name
    
    output_fd, output_path = tempfile.mkstemp(suffix=".wav")
    os.close(output_fd)
    
    try:
        subprocess.run(
            [ffmpeg_path, "-y", "-i", input_path, "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", output_path],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30
        )
        
        recognizer = sr.Recognizer()
        with sr.AudioFile(output_path) as source:
            audio = recognizer.record(source)
            
            try:
                text = recognizer.recognize_google(audio, language="es-PE")
            except:
                text = recognizer.recognize_google(audio, language="es-ES")
            
            text = _post_process_numbers(text)
            logger.info(f"[Audio] ✅ {text}")
            return text
    
    except subprocess.CalledProcessError:
        raise AudioTranscriptionError("No pude procesar el audio")
    except Exception as e:
        raise AudioTranscriptionError(str(e))
    finally:
        for p in [input_path, output_path]:
            try:
                os.remove(p)
            except:
                pass
