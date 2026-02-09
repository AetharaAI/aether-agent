"""
Speechmatics TTS Client using new SDK
================================================================================
Uses the new Speechmatics TTS API:
- URL: https://preview.tts.speechmatics.com
- Voices: sarah, theo, megan, jack
- Output: wav_16000, pcm_16000
- Endpoint: POST /generate/{voice}?output_format={format}
================================================================================
"""

import os
import logging
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)

# TTS Configuration
TTS_BASE_URL = "https://preview.tts.speechmatics.com"
TTS_API_KEY = os.getenv("SPEECHMATICS_API_KEY", "")

# Available voices
VOICES = {
    "sarah": "English (UK) female",
    "theo": "English (UK) male", 
    "megan": "English (UK) female",
    "jack": "English (US) male"
}


class SpeechmaticsTTS:
    """
    Speechmatics Text-to-Speech client using the new v1 API.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or TTS_API_KEY
        self.base_url = TTS_BASE_URL
        
    async def generate(
        self,
        text: str,
        voice: str = "sarah",
        output_format: str = "wav_16000"
    ) -> bytes:
        """
        Generate speech from text.
        
        Args:
            text: Text to convert to speech
            voice: Voice ID (sarah, theo, megan, jack)
            output_format: Audio format (wav_16000, pcm_16000)
            
        Returns:
            Audio data as bytes
        """
        if not self.api_key:
            raise RuntimeError("SPEECHMATICS_API_KEY not set")
        
        # Validate voice
        if voice not in VOICES:
            voice = "sarah"  # Default
            
        url = f"{self.base_url}/generate/{voice}"
        params = {"output_format": output_format}
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        data = {"text": text}
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                params=params,
                headers=headers,
                json=data
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise RuntimeError(f"TTS failed: {response.status} - {error_text}")
                
                return await response.read()
    
    async def stream_generate(
        self,
        text: str,
        voice: str = "sarah",
        output_format: str = "wav_16000"
    ):
        """
        Stream audio chunks as they're generated.
        Yields audio chunks for real-time playback.
        """
        if not self.api_key:
            raise RuntimeError("SPEECHMATICS_API_KEY not set")
        
        if voice not in VOICES:
            voice = "sarah"
            
        url = f"{self.base_url}/generate/{voice}"
        params = {"output_format": output_format}
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        data = {"text": text}
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                params=params,
                headers=headers,
                json=data
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise RuntimeError(f"TTS failed: {response.status} - {error_text}")
                
                # Stream chunks
                async for chunk in response.content.iter_chunked(8192):
                    if chunk:
                        yield chunk


# Singleton instance
tts_client: Optional[SpeechmaticsTTS] = None


def get_tts_client() -> SpeechmaticsTTS:
    """Get or create TTS client singleton."""
    global tts_client
    if tts_client is None:
        tts_client = SpeechmaticsTTS()
    return tts_client
