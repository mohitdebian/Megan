/**
 * useAudio — Microphone capture using MediaRecorder
 * and audio playback via Web Audio API.
 *
 * Captures audio into a single Blob and returns it as Base64 when stopped.
 */

import { useCallback, useRef, useState } from 'react';
import { base64ToArrayBuffer } from '../lib/audioUtils';

export function useAudio() {
  const [isRecording, setIsRecording] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const playbackCtxRef = useRef<AudioContext | null>(null);
  const nextPlaybackTimeRef = useRef<number>(0);

  const startRecording = useCallback(async (): Promise<void> => {
    try {
      audioChunksRef.current = [];

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });

      // Try to use a standard format
      let mimeType = 'audio/webm;codecs=opus';
      if (!MediaRecorder.isTypeSupported(mimeType)) {
        mimeType = 'audio/mp4;codecs=mp4a.40.2'; // Safari fallback
        if (!MediaRecorder.isTypeSupported(mimeType)) {
          mimeType = ''; // Let browser choose default
        }
      }

      const mediaRecorder = new MediaRecorder(stream, { mimeType: mimeType || undefined });
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          audioChunksRef.current.push(e.data);
        }
      };

      mediaRecorder.start(200); // collect 200ms chunks
      setIsRecording(true);
    } catch (err) {
      console.error('Microphone access failed:', err);
    }
  }, []);

  const stopRecording = useCallback(async (): Promise<string | null> => {
    return new Promise((resolve) => {
      const recorder = mediaRecorderRef.current;
      if (!recorder) {
        resolve(null);
        return;
      }

      recorder.onstop = () => {
        setIsRecording(false);
        // Stop all tracks to release mic
        recorder.stream.getTracks().forEach((track) => track.stop());

        const audioBlob = new Blob(audioChunksRef.current, { type: recorder.mimeType });
        audioChunksRef.current = [];
        
        // Convert Blob to Base64
        const reader = new FileReader();
        reader.onloadend = () => {
          const base64data = (reader.result as string).split(',')[1];
          resolve(base64data);
        };
        reader.onerror = () => resolve(null);
        reader.readAsDataURL(audioBlob);
      };

      if (recorder.state !== 'inactive') {
        recorder.stop();
      } else {
        resolve(null);
      }
    });
  }, []);

  const stopPlayback = useCallback(() => {
    if (playbackCtxRef.current) {
      playbackCtxRef.current.close();
      playbackCtxRef.current = null;
    }
    nextPlaybackTimeRef.current = 0;
  }, []);

  const playAudioChunk = useCallback(
    async (b64Audio: string, sampleRate: number = 24000) => {
      if (!playbackCtxRef.current || playbackCtxRef.current.state === 'closed') {
        playbackCtxRef.current = new AudioContext({ sampleRate });
        nextPlaybackTimeRef.current = playbackCtxRef.current.currentTime;
      }
      const ctx = playbackCtxRef.current;

      try {
        const audioDataBuffer = base64ToArrayBuffer(b64Audio);
        const audioBuffer = await ctx.decodeAudioData(audioDataBuffer);

        const source = ctx.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(ctx.destination);

        const currentTime = ctx.currentTime;
        const startTime = Math.max(currentTime + 0.05, nextPlaybackTimeRef.current);

        source.start(startTime);
        nextPlaybackTimeRef.current = startTime + audioBuffer.duration;
      } catch (e) {
        console.error('Audio playback error:', e);
      }
    },
    [],
  );

  return { isRecording, startRecording, stopRecording, playAudioChunk, stopPlayback };
}
