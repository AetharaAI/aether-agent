import { useState, useRef, useCallback } from "react";

interface VoiceServicesConfig {
  asrEndpoint: string;
  ttsEndpoint: string;
}

interface UseVoiceServicesReturn {
  // Speech-to-Text
  isRecording: boolean;
  startRecording: () => void;
  stopRecording: () => Promise<string>;
  audioLevel: number;
  
  // Text-to-Speech
  isTTSEnabled: boolean;
  toggleTTS: () => void;
  speak: (text: string) => Promise<void>;
  stopSpeaking: () => void;
  isSpeaking: boolean;
}

export function useVoiceServices(config: VoiceServicesConfig): UseVoiceServicesReturn {
  const [isRecording, setIsRecording] = useState(false);
  const [audioLevel, setAudioLevel] = useState(0);
  const [isTTSEnabled, setIsTTSEnabled] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const audioElementRef = useRef<HTMLAudioElement | null>(null);
  const animationFrameRef = useRef<number | null>(null);

  // Speech-to-Text functions

  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      
      // Set up audio analysis for visual feedback
      audioContextRef.current = new AudioContext();
      const source = audioContextRef.current.createMediaStreamSource(stream);
      analyserRef.current = audioContextRef.current.createAnalyser();
      analyserRef.current.fftSize = 256;
      source.connect(analyserRef.current);
      
      // Start level monitoring
      const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount);
      const updateLevel = () => {
        if (analyserRef.current && isRecording) {
          analyserRef.current.getByteFrequencyData(dataArray);
          const average = dataArray.reduce((a, b) => a + b) / dataArray.length;
          setAudioLevel(average / 255); // Normalize to 0-1
          animationFrameRef.current = requestAnimationFrame(updateLevel);
        }
      };
      updateLevel();
      
      // Set up MediaRecorder
      const mediaRecorder = new MediaRecorder(stream);
      audioChunksRef.current = [];
      
      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };
      
      mediaRecorder.start();
      mediaRecorderRef.current = mediaRecorder;
      setIsRecording(true);
    } catch (error) {
      console.error("Failed to start recording:", error);
      throw new Error("Microphone access denied or unavailable");
    }
  }, [isRecording]);

  const stopRecording = useCallback(async (): Promise<string> => {
    return new Promise((resolve, reject) => {
      if (!mediaRecorderRef.current) {
        reject(new Error("No active recording"));
        return;
      }

      mediaRecorderRef.current.onstop = async () => {
        // Stop audio level monitoring
        if (animationFrameRef.current) {
          cancelAnimationFrame(animationFrameRef.current);
        }
        if (audioContextRef.current) {
          audioContextRef.current.close();
        }
        
        setIsRecording(false);
        setAudioLevel(0);

        // Create audio blob
        const audioBlob = new Blob(audioChunksRef.current, { type: "audio/webm" });
        
        // Send to ASR service
        try {
          const formData = new FormData();
          formData.append("audio", audioBlob, "recording.webm");
          
          const response = await fetch(config.asrEndpoint, {
            method: "POST",
            body: formData,
          });
          
          if (!response.ok) {
            throw new Error(`ASR service error: ${response.statusText}`);
          }
          
          const result = await response.json();
          const transcription = result.text || result.transcription || "";
          
          resolve(transcription);
        } catch (error) {
          console.error("ASR service error:", error);
          reject(error);
        }
      };

      mediaRecorderRef.current.stop();
      
      // Stop all tracks
      if (mediaRecorderRef.current.stream) {
        mediaRecorderRef.current.stream.getTracks().forEach(track => track.stop());
      }
    });
  }, [config.asrEndpoint]);

  // Text-to-Speech functions

  const toggleTTS = useCallback(() => {
    setIsTTSEnabled(prev => !prev);
    if (isSpeaking) {
      stopSpeaking();
    }
  }, [isSpeaking]);

  const speak = useCallback(async (text: string) => {
    if (!isTTSEnabled || !text.trim()) {
      return;
    }

    try {
      setIsSpeaking(true);
      
      const response = await fetch(config.ttsEndpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ text }),
      });
      
      if (!response.ok) {
        throw new Error(`TTS service error: ${response.statusText}`);
      }
      
      // Get audio blob
      const audioBlob = await response.blob();
      const audioUrl = URL.createObjectURL(audioBlob);
      
      // Play audio
      const audio = new Audio(audioUrl);
      audioElementRef.current = audio;
      
      audio.onended = () => {
        setIsSpeaking(false);
        URL.revokeObjectURL(audioUrl);
      };
      
      audio.onerror = () => {
        setIsSpeaking(false);
        URL.revokeObjectURL(audioUrl);
      };
      
      await audio.play();
    } catch (error) {
      console.error("TTS error:", error);
      setIsSpeaking(false);
    }
  }, [isTTSEnabled, config.ttsEndpoint]);

  const stopSpeaking = useCallback(() => {
    if (audioElementRef.current) {
      audioElementRef.current.pause();
      audioElementRef.current.currentTime = 0;
      setIsSpeaking(false);
    }
  }, []);

  return {
    isRecording,
    startRecording,
    stopRecording,
    audioLevel,
    isTTSEnabled,
    toggleTTS,
    speak,
    stopSpeaking,
    isSpeaking,
  };
}
