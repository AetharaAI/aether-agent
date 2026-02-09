"use client";

import React, { useState, useRef, useCallback, useEffect } from "react";
import { cn } from "@/lib/utils";
import { Mic, Check, Loader2, X } from "lucide-react";
import { API_BASE_URL } from "@/lib/api";

interface VoiceRecorderProps {
  onTranscription: (text: string) => void;
  disabled?: boolean;
}

type RecordingState = "idle" | "recording" | "processing";

export function VoiceRecorder({ onTranscription, disabled }: VoiceRecorderProps) {
  const [state, setState] = useState<RecordingState>("idle");
  const [audioLevel, setAudioLevel] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [statusText, setStatusText] = useState("");
  
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  // Clean up on unmount
  useEffect(() => {
    return () => {
      stopRecordingCleanup();
    };
  }, []);

  const stopRecordingCleanup = () => {
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }
    mediaRecorderRef.current = null;
    setAudioLevel(0);
  };

  const startRecording = useCallback(async () => {
    try {
      setError(null);
      setStatusText("Requesting microphone access...");
      
      // Request microphone access - this will trigger browser permission prompt
      const stream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          sampleRate: 16000
        } 
      });
      
      streamRef.current = stream;
      setStatusText("Listening...");
      
      // Set up audio analysis for waveform visualization
      audioContextRef.current = new AudioContext();
      const source = audioContextRef.current.createMediaStreamSource(stream);
      analyserRef.current = audioContextRef.current.createAnalyser();
      analyserRef.current.fftSize = 256;
      analyserRef.current.smoothingTimeConstant = 0.8;
      source.connect(analyserRef.current);
      
      // Start level monitoring
      const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount);
      const updateLevel = () => {
        if (analyserRef.current && state !== "idle") {
          analyserRef.current.getByteFrequencyData(dataArray);
          // Calculate average level from frequency data
          const average = dataArray.reduce((a, b) => a + b) / dataArray.length;
          // Normalize to 0-1 with some amplification for visibility
          const normalized = Math.min(average / 128, 1);
          setAudioLevel(normalized);
          animationFrameRef.current = requestAnimationFrame(updateLevel);
        }
      };
      updateLevel();
      
      // Set up MediaRecorder
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: MediaRecorder.isTypeSupported("audio/webm") 
          ? "audio/webm" 
          : "audio/mp4"
      });
      
      audioChunksRef.current = [];
      
      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };
      
      mediaRecorder.start(100); // Collect data every 100ms
      mediaRecorderRef.current = mediaRecorder;
      setState("recording");
      
    } catch (err) {
      console.error("Failed to start recording:", err);
      setError(err instanceof Error ? err.message : "Microphone access denied");
      setState("idle");
      setStatusText("");
      stopRecordingCleanup();
    }
  }, [state]);

  const stopRecordingAndSend = useCallback(async () => {
    if (!mediaRecorderRef.current || state !== "recording") return;
    
    setState("processing");
    setStatusText("Speech detected • Transcribing...");
    
    try {
      // Stop recording
      mediaRecorderRef.current.stop();
      
      // Wait for all data to be collected
      await new Promise<void>((resolve) => {
        if (mediaRecorderRef.current) {
          mediaRecorderRef.current.onstop = () => resolve();
        } else {
          resolve();
        }
      });
      
      // Capture mimeType BEFORE cleanup
      const mimeType = mediaRecorderRef.current?.mimeType || "audio/webm";
      
      // Now clean up
      stopRecordingCleanup();
      
      // Create audio blob safely
      const audioBlob = new Blob(audioChunksRef.current, { 
        type: mimeType 
      });
      
      // Send to backend for transcription
      const formData = new FormData();
      formData.append("audio", audioBlob, "recording.webm");
      formData.append("language", "en");
      
      const response = await fetch(`${API_BASE_URL}/api/voice/transcribe`, {
        method: "POST",
        body: formData,
      });
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: "Transcription failed" }));
        throw new Error(errorData.detail || `Error: ${response.status}`);
      }
      
      const result = await response.json();
      const transcription = result.text || "";
      
      if (transcription.trim()) {
        onTranscription(transcription);
      } else {
        setError("No speech detected");
      }
      
    } catch (err) {
      console.error("Transcription error:", err);
      setError(err instanceof Error ? err.message : "Transcription failed");
    } finally {
      setState("idle");
      setStatusText("");
    }
  }, [state, onTranscription]);

  const cancelRecording = useCallback(() => {
    if (mediaRecorderRef.current) {
      mediaRecorderRef.current.stop();
    }
    stopRecordingCleanup();
    setState("idle");
    setStatusText("");
    setError(null);
  }, []);

  // Generate waveform bars
  const renderWaveform = () => {
    const bars = 12;
    return (
      <div className="flex items-center justify-center gap-0.5 h-6">
        {Array.from({ length: bars }).map((_, i) => {
          // Create a wave effect based on audio level
          const phase = (Date.now() / 200) + (i / bars) * Math.PI * 2;
          const baseHeight = audioLevel * 100;
          const waveEffect = Math.sin(phase) * 0.3 + 0.7;
          const height = Math.max(8, baseHeight * waveEffect * (0.5 + Math.random() * 0.5));
          
          return (
            <div
              key={i}
              className={cn(
                "w-1 rounded-full transition-all duration-75",
                audioLevel > 0.1 ? "bg-orange-500" : "bg-gray-500"
              )}
              style={{
                height: `${height}%`,
                animationDelay: `${i * 0.05}s`
              }}
            />
          );
        })}
      </div>
    );
  };

  return (
    <div className="relative">
      {/* Error tooltip */}
      {error && state === "idle" && (
        <div className="absolute bottom-full mb-2 left-1/2 -translate-x-1/2 whitespace-nowrap">
          <div className="bg-red-500/90 text-white text-xs px-2 py-1 rounded flex items-center gap-1">
            <span>{error}</span>
            <button onClick={() => setError(null)} className="hover:text-red-200">
              <X className="w-3 h-3" />
            </button>
          </div>
        </div>
      )}
      
      {/* Main button area */}
      <div className="flex items-center gap-2">
        {/* Status text */}
        {state !== "idle" && (
          <span className={cn(
            "text-xs transition-all",
            state === "recording" ? "text-orange-400" : "text-blue-400"
          )}>
            {statusText}
          </span>
        )}
        
        {/* Waveform visualization - only when recording */}
        {state === "recording" && (
          <div className="w-16">
            {renderWaveform()}
          </div>
        )}
        
        {/* Spinner when processing */}
        {state === "processing" && (
          <Loader2 className="w-4 h-4 animate-spin text-blue-400" />
        )}
        
        {/* Main button */}
        {state === "idle" ? (
          // Mic button - start recording
          <button
            onClick={startRecording}
            disabled={disabled}
            className={cn(
              "p-2 rounded-lg transition-all",
              disabled 
                ? "text-gray-600 cursor-not-allowed" 
                : "text-gray-400 hover:text-orange-400 hover:bg-orange-500/10"
            )}
            title="Click to start recording"
          >
            <Mic className="w-4 h-4" />
          </button>
        ) : state === "recording" ? (
          // Checkmark button - stop and send
          <button
            onClick={stopRecordingAndSend}
            className="p-2 rounded-lg bg-orange-600 text-white hover:bg-orange-500 transition-all animate-in zoom-in"
            title="Click to send"
          >
            <Check className="w-4 h-4" />
          </button>
        ) : (
          // Processing state - disabled button
          <button
            disabled
            className="p-2 rounded-lg bg-blue-600/50 text-white/50 cursor-not-allowed"
          >
            <Loader2 className="w-4 h-4 animate-spin" />
          </button>
        )}
        
        {/* Cancel button when recording */}
        {state === "recording" && (
          <button
            onClick={cancelRecording}
            className="p-1.5 rounded-lg text-gray-400 hover:text-red-400 hover:bg-red-500/10 transition-all"
            title="Cancel"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        )}
      </div>
    </div>
  );
}

export default VoiceRecorder;
