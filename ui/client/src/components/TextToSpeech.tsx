"use client";

import React, { useState, useRef, useCallback } from "react";
import { cn } from "@/lib/utils";
import { Volume2, VolumeX, Loader2 } from "lucide-react";
import { API_BASE_URL } from "@/lib/api";

interface TextToSpeechProps {
  text: string;
  className?: string;
}

type TTSState = "idle" | "loading" | "playing";

export function TextToSpeech({ text, className }: TextToSpeechProps) {
  const [state, setState] = useState<TTSState>("idle");
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const stopSpeaking = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      audioRef.current = null;
    }
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setState("idle");
  }, []);

  const speak = useCallback(async () => {
    if (!text.trim() || state === "loading") return;
    
    // If already playing, stop
    if (state === "playing") {
      stopSpeaking();
      return;
    }
    
    setState("loading");
    abortControllerRef.current = new AbortController();
    
    try {
      // Limit text length for TTS
      const maxLength = 500;
      const textToSpeak = text.length > maxLength 
        ? text.slice(0, maxLength) + "..." 
        : text;
      
      const response = await fetch(`${API_BASE_URL}/api/voice/speak`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          text: textToSpeak,
          voice: "en-US",
          sample_rate: 22050
        }),
        signal: abortControllerRef.current.signal
      });
      
      if (!response.ok) {
        throw new Error("TTS failed");
      }
      
      // Get audio blob and play
      const audioBlob = await response.blob();
      const audioUrl = URL.createObjectURL(audioBlob);
      
      const audio = new Audio(audioUrl);
      audioRef.current = audio;
      
      audio.onended = () => {
        URL.revokeObjectURL(audioUrl);
        setState("idle");
        audioRef.current = null;
      };
      
      audio.onerror = () => {
        URL.revokeObjectURL(audioUrl);
        setState("idle");
        audioRef.current = null;
      };
      
      setState("playing");
      await audio.play();
      
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") {
        // Request was cancelled, already handled
        return;
      }
      console.error("TTS error:", err);
      setState("idle");
    }
  }, [text, state, stopSpeaking]);

  return (
    <button
      onClick={speak}
      disabled={!text.trim() || state === "loading"}
      className={cn(
        "p-1.5 rounded-lg transition-all",
        state === "playing" && "text-orange-400 bg-orange-500/10",
        state === "idle" && "text-gray-400 hover:text-gray-300 hover:bg-white/5",
        state === "loading" && "text-gray-500 cursor-not-allowed",
        className
      )}
      title={state === "playing" ? "Stop speaking" : "Read aloud"}
    >
      {state === "loading" ? (
        <Loader2 className="w-3.5 h-3.5 animate-spin" />
      ) : state === "playing" ? (
        <VolumeX className="w-3.5 h-3.5" />
      ) : (
        <Volume2 className="w-3.5 h-3.5" />
      )}
    </button>
  );
}

export default TextToSpeech;
