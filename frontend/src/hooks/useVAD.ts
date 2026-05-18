/**
 * useVAD — Voice Activity Detection for hands-free conversation.
 *
 * Uses Web Audio API AnalyserNode to detect speech vs silence.
 * When speech is detected → starts recording.
 * When silence persists for SILENCE_THRESHOLD_MS → stops and returns audio.
 *
 * This enables a natural "talk and response" flow without clicking buttons.
 */

import { useCallback, useRef, useState } from 'react';

/** Minimum RMS volume to consider as speech (0-1 range, tune for your mic) */
const SPEECH_THRESHOLD = 0.035;

/** How long silence must persist before we consider the utterance done (ms) */
const SILENCE_THRESHOLD_MS = 1500;

/** Minimum speech duration to avoid sending noise bursts (ms) */
const MIN_SPEECH_DURATION_MS = 600;

/** How often we check the audio level (ms) */
const CHECK_INTERVAL_MS = 60;

export interface VADState {
  /** Whether VAD mode is active (listening for speech) */
  isActive: boolean;
  /** Whether user is currently speaking */
  isSpeaking: boolean;
}

export function useVAD() {
  const [isActive, setIsActive] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);

  const streamRef = useRef<MediaStream | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const checkIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Timing refs
  const speechStartRef = useRef<number>(0);
  const lastSpeechRef = useRef<number>(0);
  const isCurrentlySpeakingRef = useRef(false);

  // Callback to handle completed utterance
  const onUtteranceRef = useRef<((b64Audio: string) => void) | null>(null);

  // Pause ref — when Megan is speaking, pause VAD detection
  const pausedRef = useRef(false);
  const activeRef = useRef(false);

  /**
   * Get the RMS (root mean square) volume from the analyser.
   */
  const getRMS = useCallback((): number => {
    const analyser = analyserRef.current;
    if (!analyser) return 0;

    const data = new Float32Array(analyser.fftSize);
    analyser.getFloatTimeDomainData(data);

    let sumSq = 0;
    for (let i = 0; i < data.length; i++) {
      sumSq += data[i] * data[i];
    }
    return Math.sqrt(sumSq / data.length);
  }, []);

  /**
   * Start the MediaRecorder to capture an utterance.
   */
  const startCapture = useCallback(() => {
    const stream = streamRef.current;
    if (!stream) return;

    chunksRef.current = [];

    let mimeType = 'audio/webm;codecs=opus';
    if (!MediaRecorder.isTypeSupported(mimeType)) {
      mimeType = 'audio/mp4;codecs=mp4a.40.2';
      if (!MediaRecorder.isTypeSupported(mimeType)) {
        mimeType = '';
      }
    }

    const recorder = new MediaRecorder(stream, { mimeType: mimeType || undefined });
    mediaRecorderRef.current = recorder;

    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) {
        chunksRef.current.push(e.data);
      }
    };

    recorder.start(200);
  }, []);

  /**
   * Stop the MediaRecorder and return audio as base64.
   */
  const stopCapture = useCallback((): Promise<string | null> => {
    return new Promise((resolve) => {
      const recorder = mediaRecorderRef.current;
      if (!recorder || recorder.state === 'inactive') {
        resolve(null);
        return;
      }

      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType });
        chunksRef.current = [];

        const reader = new FileReader();
        reader.onloadend = () => {
          const b64 = (reader.result as string).split(',')[1];
          resolve(b64);
        };
        reader.onerror = () => resolve(null);
        reader.readAsDataURL(blob);
      };

      recorder.stop();
    });
  }, []);

  /**
   * The main VAD check loop — runs every CHECK_INTERVAL_MS.
   */
  const startVADLoop = useCallback(() => {
    checkIntervalRef.current = setInterval(async () => {
      if (pausedRef.current || !activeRef.current) return;

      const rms = getRMS();
      const now = Date.now();

      if (rms > SPEECH_THRESHOLD) {
        // Speech detected
        lastSpeechRef.current = now;

        if (!isCurrentlySpeakingRef.current) {
          // Transition: silence → speaking
          isCurrentlySpeakingRef.current = true;
          speechStartRef.current = now;
          setIsSpeaking(true);
          startCapture();
        }
      } else {
        // Silence
        if (isCurrentlySpeakingRef.current) {
          const silenceDuration = now - lastSpeechRef.current;
          const speechDuration = now - speechStartRef.current;

          if (silenceDuration >= SILENCE_THRESHOLD_MS) {
            // User stopped talking — finalize utterance
            isCurrentlySpeakingRef.current = false;
            setIsSpeaking(false);

            if (speechDuration >= MIN_SPEECH_DURATION_MS) {
              const b64 = await stopCapture();
              if (b64 && onUtteranceRef.current) {
                onUtteranceRef.current(b64);
              }
            } else {
              // Too short, discard (probably noise)
              await stopCapture();
            }
          }
        }
      }
    }, CHECK_INTERVAL_MS);
  }, [getRMS, startCapture, stopCapture]);

  /**
   * Start VAD — opens microphone and begins monitoring.
   */
  const startVAD = useCallback(
    async (onUtterance: (b64Audio: string) => void) => {
      if (activeRef.current) return;

      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            channelCount: 1,
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
          },
        });

        streamRef.current = stream;
        onUtteranceRef.current = onUtterance;

        // Set up audio analysis
        const audioCtx = new AudioContext();
        audioCtxRef.current = audioCtx;

        const source = audioCtx.createMediaStreamSource(stream);
        const analyser = audioCtx.createAnalyser();
        analyser.fftSize = 2048;
        analyser.smoothingTimeConstant = 0.3;
        source.connect(analyser);
        analyserRef.current = analyser;

        activeRef.current = true;
        pausedRef.current = false;
        setIsActive(true);
        setIsSpeaking(false);

        startVADLoop();
      } catch (err) {
        console.error('[VAD] Microphone access failed:', err);
      }
    },
    [startVADLoop]
  );

  /**
   * Stop VAD — closes microphone and stops monitoring.
   */
  const stopVAD = useCallback(() => {
    activeRef.current = false;
    setIsActive(false);
    setIsSpeaking(false);
    isCurrentlySpeakingRef.current = false;

    if (checkIntervalRef.current) {
      clearInterval(checkIntervalRef.current);
      checkIntervalRef.current = null;
    }

    // Stop any ongoing recording
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }
    mediaRecorderRef.current = null;

    // Close audio context
    if (audioCtxRef.current) {
      audioCtxRef.current.close();
      audioCtxRef.current = null;
    }
    analyserRef.current = null;

    // Release microphone
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }

    chunksRef.current = [];
    onUtteranceRef.current = null;
  }, []);

  /**
   * Pause VAD detection (e.g., while Megan is speaking to avoid echo).
   */
  const pauseVAD = useCallback(() => {
    pausedRef.current = true;
    // If we were mid-utterance, cancel it
    if (isCurrentlySpeakingRef.current) {
      isCurrentlySpeakingRef.current = false;
      setIsSpeaking(false);
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
        mediaRecorderRef.current.stop();
      }
      chunksRef.current = [];
    }
  }, []);

  /**
   * Resume VAD detection (e.g., after Megan finishes speaking).
   */
  const resumeVAD = useCallback(() => {
    pausedRef.current = false;
  }, []);

  return {
    isActive,
    isSpeaking,
    startVAD,
    stopVAD,
    pauseVAD,
    resumeVAD,
  };
}
