# Voice Services Configuration Guide

This guide explains how to configure the Aether UI to work with your existing ASR (Automatic Speech Recognition) and TTS (Text-to-Speech) services.

## Environment Variables

The Aether UI requires two environment variables to connect to your voice services:

### VITE_ASR_ENDPOINT

Your ASR/VAD service endpoint for speech-to-text conversion.

**Expected API format:**
- Method: `POST`
- Content-Type: `multipart/form-data`
- Body: Audio file with field name `audio`
- Response: JSON with `text` or `transcription` field

**Example response:**
```json
{
  "text": "Hello, this is the transcribed text",
  "confidence": 0.95
}
```

**Default:** `http://localhost:8001/asr`

### VITE_TTS_ENDPOINT

Your TTS service endpoint for text-to-speech synthesis.

**Expected API format:**
- Method: `POST`
- Content-Type: `application/json`
- Body: `{"text": "Text to speak"}`
- Response: Audio blob (mp3, wav, ogg, etc.)

**Example request:**
```json
{
  "text": "Hello, this is the text to be spoken"
}
```

**Default:** `http://localhost:8002/tts`

## Configuration Examples

### Local Setup

If you're running services locally:

```bash
# In Manus Settings → Secrets for this project
VITE_ASR_ENDPOINT=http://localhost:8001/asr
VITE_TTS_ENDPOINT=http://localhost:8002/tts
```

### Cloud Setup

If you're using cloud-hosted services:

```bash
VITE_ASR_ENDPOINT=https://your-asr-service.com/api/transcribe
VITE_TTS_ENDPOINT=https://your-tts-service.com/api/speak
```

### Mixed Setup (Local ASR + Cloud TTS)

```bash
VITE_ASR_ENDPOINT=http://localhost:8001/asr
VITE_TTS_ENDPOINT=https://your-tts-service.com/api/speak
```

## Compatible Services

### ASR Services

The following ASR services are compatible (with appropriate API wrappers):

- **Whisper** (OpenAI) - via faster-whisper or whisper.cpp
- **Vosk** - offline speech recognition
- **DeepSpeech** - Mozilla's speech recognition
- **Google Cloud Speech-to-Text** - with API wrapper
- **Azure Speech Services** - with API wrapper
- **Custom VAD + ASR pipeline**

### TTS Services

The following TTS services are compatible:

- **Piper** - fast, local neural TTS
- **Coqui TTS** - open-source TTS
- **eSpeak NG** - lightweight TTS
- **Google Cloud Text-to-Speech** - with API wrapper
- **Azure Speech Services** - with API wrapper
- **ElevenLabs** - with API wrapper
- **Custom TTS models**

## API Wrapper Examples

If your service doesn't match the expected format, you can create a simple wrapper.

### Python FastAPI Wrapper for Whisper

```python
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
import whisper

app = FastAPI()
model = whisper.load_model("base")

@app.post("/asr")
async def transcribe(audio: UploadFile = File(...)):
    # Save uploaded file
    with open("temp.webm", "wb") as f:
        f.write(await audio.read())
    
    # Transcribe
    result = model.transcribe("temp.webm")
    
    return JSONResponse({"text": result["text"]})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
```

### Python FastAPI Wrapper for Piper TTS

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import subprocess
import io

app = FastAPI()

class TTSRequest(BaseModel):
    text: str

@app.post("/tts")
async def synthesize(request: TTSRequest):
    # Run piper TTS
    process = subprocess.Popen(
        ["piper", "--model", "en_US-lessac-medium", "--output_raw"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )
    
    audio_data, _ = process.communicate(request.text.encode())
    
    return StreamingResponse(
        io.BytesIO(audio_data),
        media_type="audio/wav"
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
```

## Testing Your Setup

### Test ASR Endpoint

```bash
# Record a short audio clip and test
curl -X POST http://localhost:8001/asr \
  -F "audio=@test.webm" \
  | jq .text
```

### Test TTS Endpoint

```bash
# Test TTS and save output
curl -X POST http://localhost:8002/tts \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello, this is a test"}' \
  --output test.mp3

# Play the audio
mpv test.mp3
```

## Usage in Aether UI

### Speech-to-Text

1. Click the microphone button (🎤) in the input area
2. Speak your message
3. Click the checkmark (✓) when finished
4. The transcribed text will appear in the input field
5. Press Enter or click Send to submit

### Text-to-Speech

1. Click the speaker button (🔊) to enable TTS
2. Agent responses will be automatically spoken
3. Click the muted speaker button (🔇) to disable TTS
4. TTS can be toggled on/off at any time

## Troubleshooting

### Microphone Access Denied

- Check browser permissions for microphone access
- Ensure you're using HTTPS or localhost (required for getUserMedia)
- Try a different browser

### ASR Service Not Responding

- Verify the service is running: `curl http://localhost:8001/health`
- Check CORS headers if running on different domain
- Verify the audio format is supported by your service

### TTS Audio Not Playing

- Check browser console for errors
- Verify the TTS service returns valid audio format
- Test the endpoint directly with curl
- Check audio codec support in your browser

### Poor Transcription Quality

- Ensure good microphone quality
- Reduce background noise
- Use a better ASR model (e.g., Whisper large)
- Check audio sample rate and bitrate

## Advanced Configuration

### Custom Audio Format

If you need to use a specific audio format, modify `useVoiceServices.ts`:

```typescript
// Change MediaRecorder options
const mediaRecorder = new MediaRecorder(stream, {
  mimeType: 'audio/webm;codecs=opus',
  audioBitsPerSecond: 128000,
});
```

### VAD (Voice Activity Detection)

For better UX, implement VAD to auto-stop recording:

```typescript
// In useVoiceServices.ts, add VAD logic
const checkSilence = () => {
  if (audioLevel < 0.01 && silenceDuration > 2000) {
    stopRecording();
  }
};
```

### Streaming ASR

For real-time transcription, implement WebSocket-based streaming:

```typescript
// Use WebSocket instead of HTTP POST
const ws = new WebSocket('ws://localhost:8001/asr/stream');
ws.send(audioChunk);
```

## Security Considerations

- **HTTPS Required**: Microphone access requires HTTPS in production
- **API Keys**: Store API keys securely in environment variables
- **CORS**: Configure CORS properly for cross-origin requests
- **Rate Limiting**: Implement rate limiting on your services
- **Audio Privacy**: Audio data should be transmitted securely

## Performance Tips

- Use local services for lower latency
- Implement audio compression before upload
- Cache TTS responses for repeated phrases
- Use WebSocket for streaming ASR
- Optimize model size vs. quality tradeoff
