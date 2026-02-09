"""
Speechmatics Voice Services API

================================================================================
Provides STT (Speech-to-Text) and TTS (Text-to-Speech) endpoints using 
Speechmatics enterprise-grade voice APIs.

Features:
- Batch transcription for recorded audio (with automatic format conversion)
- Text-to-Speech synthesis

API Endpoints:
- POST /api/voice/transcribe - Upload audio file for transcription
- POST /api/voice/speak - Convert text to speech
- GET /api/voice/status - Check voice services availability
- GET /api/voice/languages - List supported languages
================================================================================
"""

import os
import io
import json
import logging
import tempfile
import subprocess
from typing import Optional, Tuple
from pathlib import Path

import aiohttp
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# API Configuration
SPEECHMATICS_API_KEY = os.getenv("SPEECHMATICS_API_KEY", "")

# Create router
router = APIRouter(prefix="/api/voice", tags=["voice"])


# ============================================================================
# Pydantic Models
# ============================================================================

class TextToSpeechRequest(BaseModel):
    text: str
    voice: str = "en-US"
    sample_rate: int = 22050


class VoiceStatusResponse(BaseModel):
    stt_available: bool
    tts_available: bool
    provider: str = "Speechmatics"


# ============================================================================
# Audio Conversion Utility
# ============================================================================

def convert_audio_to_wav(input_data: bytes, input_format: str = "webm") -> bytes:
    """
    Convert audio to WAV format using ffmpeg.
    Speechmatics supports: WAV, MP3, OGG, M4A, FLAC
    """
    try:
        # Write input to temp file
        with tempfile.NamedTemporaryFile(suffix=f"." + input_format.replace("audio/", "").replace(";codecs=opus", ""), delete=False) as input_file:
            input_file.write(input_data)
            input_path = input_file.name
        
        # Create output temp file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as output_file:
            output_path = output_file.name
        
        # Convert using ffmpeg
        cmd = [
            "ffmpeg",
            "-y",  # Overwrite output
            "-i", input_path,
            "-ar", "16000",  # Sample rate 16kHz
            "-ac", "1",      # Mono
            "-c:a", "pcm_s16le",  # 16-bit PCM
            output_path
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            logger.error(f"ffmpeg error: {result.stderr}")
            raise HTTPException(
                status_code=400,
                detail=f"Audio conversion failed: {result.stderr}"
            )
        
        # Read converted audio
        with open(output_path, "rb") as f:
            wav_data = f.read()
        
        # Cleanup
        os.unlink(input_path)
        os.unlink(output_path)
        
        return wav_data
        
    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=500,
            detail="Audio conversion timeout"
        )
    except Exception as e:
        logger.error(f"Audio conversion error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Audio conversion failed: {str(e)}"
        )


# ============================================================================
# Speechmatics TTS Configuration
# ============================================================================

TTS_VOICES = {
    "sarah": {"name": "Sarah", "locale": "en-GB", "gender": "female"},
    "theo": {"name": "Theo", "locale": "en-GB", "gender": "male"},
    "megan": {"name": "Megan", "locale": "en-GB", "gender": "female"},
    "jack": {"name": "Jack", "locale": "en-US", "gender": "male"},
}


# ============================================================================
# Speechmatics Client using official SDK
# ============================================================================

class SpeechmaticsService:
    """Service wrapper for Speechmatics APIs"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://asr.api.speechmatics.com/v2"
        self.tts_url = "https://preview.tts.speechmatics.com"  # New TTS endpoint
    
    async def transcribe(
        self, 
        audio_data: bytes, 
        filename: str = "audio.wav",
        language: str = "en"
    ) -> dict:
        """
        Submit audio for batch transcription using Speechmatics REST API.
        """
        async with aiohttp.ClientSession() as session:
            # Step 1: Create a job
            job_config = {
                "type": "transcription",
                "transcription_config": {
                    "language": language,
                    "operating_point": "enhanced",
                    "punctuation_overrides": {
                        "allowed_marks": [".", ",", "?", "!", ";", ":", "-", "'", '"']
                    }
                }
            }
            
            data = aiohttp.FormData()
            data.add_field(
                "data_file",
                io.BytesIO(audio_data),
                filename=filename,
                content_type="audio/wav"
            )
            data.add_field("config", json.dumps(job_config))
            
            headers = {"Authorization": f"Bearer {self.api_key}"}
            
            async with session.post(
                f"{self.base_url}/jobs",
                headers=headers,
                data=data
            ) as response:
                if response.status != 201:
                    error_text = await response.text()
                    raise HTTPException(
                        status_code=response.status,
                        detail=f"Speechmatics job creation failed: {error_text}"
                    )
                
                job_result = await response.json()
                job_id = job_result.get("id")
                
                if not job_id:
                    raise HTTPException(
                        status_code=500,
                        detail="No job ID returned from Speechmatics"
                    )
                
                logger.info(f"Created Speechmatics job: {job_id}")
                
                # Step 2: Poll for results
                import asyncio
                max_attempts = 60
                for attempt in range(max_attempts):
                    await asyncio.sleep(1)
                    
                    async with session.get(
                        f"{self.base_url}/jobs/{job_id}",
                        headers=headers
                    ) as status_response:
                        if status_response.status == 200:
                            status_data = await status_response.json()
                            job_status = status_data.get("job", {}).get("status")
                            
                            if job_status == "done":
                                # Get results
                                async with session.get(
                                    f"{self.base_url}/jobs/{job_id}/transcript",
                                    headers=headers
                                ) as result_response:
                                    if result_response.status == 200:
                                        transcript_data = await result_response.json()
                                        return self._parse_transcript(transcript_data)
                                    else:
                                        raise HTTPException(
                                            status_code=result_response.status,
                                            detail="Failed to fetch transcript"
                                        )
                            elif job_status in {"rejected", "expired", "unsupported_file_format"}:
                                raise HTTPException(
                                    status_code=400,
                                    detail=f"Job failed with status: {job_status}"
                                )
                        
                raise HTTPException(
                    status_code=504,
                    detail="Transcription timeout"
                )
    
    def _parse_transcript(self, data: dict) -> dict:
        """Parse Speechmatics transcript format"""
        results = data.get("results", [])
        
        words = []
        full_text_parts = []
        
        for result in results:
            alternatives = result.get("alternatives", [])
            if alternatives:
                word = alternatives[0]
                words.append({
                    "word": word.get("content", ""),
                    "start": word.get("start_time", 0),
                    "end": word.get("end_time", 0),
                    "confidence": word.get("confidence", 0)
                })
                full_text_parts.append(word.get("content", ""))
        
        full_text = " ".join(full_text_parts)
        avg_confidence = sum(w["confidence"] for w in words) / len(words) if words else 0
        duration = words[-1]["end"] if words else 0
        
        return {
            "text": full_text,
            "confidence": round(avg_confidence, 3),
            "duration": round(duration, 2),
            "words": words
        }
    
    async def text_to_speech(
        self, 
        text: str, 
        voice: str = "sarah",
        output_format: str = "wav_16000"
    ) -> bytes:
        """
        Convert text to speech using new Speechmatics TTS API.
        
        Args:
            text: Text to synthesize
            voice: Voice ID (sarah, theo, megan, jack)
            output_format: Audio format (wav_16000, pcm_16000)
        """
        # Validate voice
        if voice not in TTS_VOICES:
            voice = "sarah"  # Default
        
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {"text": text}
            
            url = f"{self.tts_url}/generate/{voice}"
            params = {"output_format": output_format}
            
            async with session.post(
                url,
                headers=headers,
                params=params,
                json=payload
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise HTTPException(
                        status_code=response.status,
                        detail=f"TTS failed: {error_text}"
                    )
                
                return await response.read()


# Initialize service if API key is available
service: Optional[SpeechmaticsService] = None
if SPEECHMATICS_API_KEY:
    service = SpeechmaticsService(SPEECHMATICS_API_KEY)
    logger.info("Speechmatics service initialized")
else:
    logger.warning("SPEECHMATICS_API_KEY not set - voice services disabled")


# ============================================================================
# REST API Endpoints
# ============================================================================

@router.get("/status", response_model=VoiceStatusResponse)
async def get_voice_status():
    """Check if voice services are available"""
    return VoiceStatusResponse(
        stt_available=service is not None,
        tts_available=service is not None
    )


@router.post("/transcribe")
async def transcribe_audio(
    audio: UploadFile = File(...),
    language: str = "en"
):
    """
    Upload an audio file for transcription.
    
    Accepts any format (WebM, MP3, etc.) - automatically converts to WAV.
    Max size: 10MB
    """
    if not service:
        raise HTTPException(
            status_code=503,
            detail="Speechmatics not configured. Set SPEECHMATICS_API_KEY."
        )
    
    try:
        # Read audio data
        audio_data = await audio.read()
        
        if len(audio_data) > 10 * 1024 * 1024:  # 10MB limit
            raise HTTPException(
                status_code=400,
                detail="Audio file too large. Max size: 10MB"
            )
        
        # Detect input format from content type or filename
        content_type = audio.content_type or ""
        filename = audio.filename or "audio.webm"
        
        logger.info(f"Received audio: {filename}, type: {content_type}, size: {len(audio_data)} bytes")
        
        # Convert to WAV if needed
        if "webm" in content_type.lower() or "opus" in content_type.lower() or filename.endswith(".webm"):
            logger.info("Converting WebM/Opus to WAV...")
            audio_data = convert_audio_to_wav(audio_data, "webm")
            filename = "audio.wav"
        elif "mp3" in content_type.lower() or filename.endswith(".mp3"):
            audio_data = convert_audio_to_wav(audio_data, "mp3")
            filename = "audio.wav"
        elif "ogg" in content_type.lower() or filename.endswith(".ogg"):
            audio_data = convert_audio_to_wav(audio_data, "ogg")
            filename = "audio.wav"
        elif "m4a" in content_type.lower() or "mp4" in content_type.lower() or filename.endswith(".m4a"):
            audio_data = convert_audio_to_wav(audio_data, "m4a")
            filename = "audio.wav"
        
        # Transcribe
        result = await service.transcribe(
            audio_data=audio_data,
            filename=filename,
            language=language
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Transcription failed: {str(e)}"
        )


@router.post("/speak")
async def text_to_speech_endpoint(
    text: str = "",
    voice: str = "sarah"
):
    """
    Convert text to speech.
    
    Available voices: sarah (en-GB female), theo (en-GB male), 
    megan (en-GB female), jack (en-US male)
    """
    if not service:
        raise HTTPException(
            status_code=503,
            detail="Speechmatics not configured."
        )
    
    if not text.strip():
        raise HTTPException(
            status_code=400,
            detail="Text cannot be empty"
        )
    
    try:
        if len(text) > 5000:
            text = text[:5000]
        
        audio_data = await service.text_to_speech(
            text=text,
            voice=voice
        )
        
        return StreamingResponse(
            io.BytesIO(audio_data),
            media_type="audio/wav",
            headers={"Content-Disposition": 'attachment; filename="speech.wav"'}
        )
        
    except Exception as e:
        logger.error(f"TTS error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Text-to-speech failed: {str(e)}"
        )


@router.get("/languages")
async def list_languages():
    """List supported languages and voices"""
    return {
        "stt": [
            {"code": "en", "name": "English"},
            {"code": "es", "name": "Spanish"},
            {"code": "fr", "name": "French"},
            {"code": "de", "name": "German"},
            {"code": "it", "name": "Italian"},
            {"code": "pt", "name": "Portuguese"},
            {"code": "nl", "name": "Dutch"},
            {"code": "ja", "name": "Japanese"},
            {"code": "ko", "name": "Korean"},
            {"code": "zh", "name": "Chinese"},
        ],
        "tts": [
            {"id": "sarah", "name": "Sarah", "locale": "en-GB", "gender": "female"},
            {"id": "theo", "name": "Theo", "locale": "en-GB", "gender": "male"},
            {"id": "megan", "name": "Megan", "locale": "en-GB", "gender": "female"},
            {"id": "jack", "name": "Jack", "locale": "en-US", "gender": "male"},
        ]
    }
