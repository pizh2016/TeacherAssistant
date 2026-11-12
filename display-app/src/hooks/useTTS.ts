/**
 * Web Speech API TTS hook
 *
 * 离线语音播报，支持中英文。
 * 支持重复播报（tts_repeat 1-3 次）。
 * 对齐 docs/00 §5.5 Web Speech API 语音播报方案。
 */

import { useCallback, useEffect, useRef, useState } from "react";

interface UseTTSReturn {
  speak: (text: string, repeat?: number) => void;
  stop: () => void;
  isSpeaking: boolean;
  isSupported: boolean;
  ttsRepeatCurrent: number;
  ttsRepeatTotal: number;
}

export function useTTS(): UseTTSReturn {
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [ttsRepeatCurrent, setTtsRepeatCurrent] = useState(0);
  const [ttsRepeatTotal, setTtsRepeatTotal] = useState(0);
  const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null);
  const repeatTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isSupported =
    typeof window !== "undefined" && "speechSynthesis" in window;

  // 预加载语音列表
  useEffect(() => {
    if (!isSupported) return;
    // 某些浏览器需要触发一次 getVoices 才能加载
    window.speechSynthesis.getVoices();
    window.speechSynthesis.onvoiceschanged = () => {
      window.speechSynthesis.getVoices();
    };
    return () => {
      window.speechSynthesis.cancel();
      if (repeatTimerRef.current) clearTimeout(repeatTimerRef.current);
    };
  }, [isSupported]);

  const speak = useCallback(
    (text: string, repeat: number = 1) => {
      if (!isSupported || !text) return;

      // 取消正在进行的播报
      window.speechSynthesis.cancel();
      if (repeatTimerRef.current) {
        clearTimeout(repeatTimerRef.current);
        repeatTimerRef.current = null;
      }

      const total = Math.max(1, Math.min(3, repeat));
      setTtsRepeatTotal(total);
      setTtsRepeatCurrent(1);

      const doSpeak = (iteration: number) => {
        setTtsRepeatCurrent(iteration);
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = "zh-CN";
        utterance.rate = 1.0;
        utterance.pitch = 1.0;
        utterance.volume = 1.0;

        // 选择中文语音
        const voices = window.speechSynthesis.getVoices();
        const zhVoice = voices.find((v) => v.lang.startsWith("zh"));
        if (zhVoice) {
          utterance.voice = zhVoice;
        }

        utterance.onstart = () => setIsSpeaking(true);
        utterance.onend = () => {
          if (iteration < total) {
            // 间隔 1.5 秒后重复播报
            repeatTimerRef.current = setTimeout(() => {
              doSpeak(iteration + 1);
            }, 1500);
          } else {
            setIsSpeaking(false);
            setTtsRepeatCurrent(0);
            setTtsRepeatTotal(0);
          }
        };
        utterance.onerror = () => {
          setIsSpeaking(false);
          setTtsRepeatCurrent(0);
          setTtsRepeatTotal(0);
        };

        utteranceRef.current = utterance;
        window.speechSynthesis.speak(utterance);
      };

      doSpeak(1);
    },
    [isSupported],
  );

  const stop = useCallback(() => {
    if (!isSupported) return;
    window.speechSynthesis.cancel();
    if (repeatTimerRef.current) {
      clearTimeout(repeatTimerRef.current);
      repeatTimerRef.current = null;
    }
    setIsSpeaking(false);
    setTtsRepeatCurrent(0);
    setTtsRepeatTotal(0);
  }, [isSupported]);

  return { speak, stop, isSpeaking, isSupported, ttsRepeatCurrent, ttsRepeatTotal };
}
