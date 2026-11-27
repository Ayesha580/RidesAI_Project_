import { useEffect, useRef, useState } from "react";

/** Browser-native voice I/O for the shared business AI conversation pipeline.
 * Speech recognition is provided by the browser (where available); the resulting
 * transcript is sent through the same authenticated/public AI API as typed text.
 * Speech synthesis reads the actual assistant response returned by that API.
 */
export default function VoiceControls({ onTranscript, speechText, disabled = false }) {
  const recognitionRef = useRef(null);
  const [listening, setListening] = useState(false);
  const [voiceError, setVoiceError] = useState("");
  const SpeechRecognition = typeof window !== "undefined"
    ? (window.SpeechRecognition || window.webkitSpeechRecognition) : null;
  const canSpeak = typeof window !== "undefined" && "speechSynthesis" in window;

  useEffect(() => () => {
    try { recognitionRef.current?.stop(); } catch { /* already stopped */ }
    if (canSpeak) window.speechSynthesis.cancel();
  }, [canSpeak]);

  const startListening = () => {
    setVoiceError("");
    if (!SpeechRecognition) {
      setVoiceError("Voice input is not supported in this browser. Use Chrome or Edge, or type your message.");
      return;
    }
    try {
      const recognition = new SpeechRecognition();
      recognition.lang = navigator.language || "en-US";
      recognition.interimResults = false;
      recognition.maxAlternatives = 1;
      recognition.onresult = (event) => {
        const transcript = event.results?.[0]?.[0]?.transcript?.trim();
        if (transcript) onTranscript(transcript);
      };
      recognition.onerror = (event) => setVoiceError(event.error === "not-allowed"
        ? "Microphone permission was denied. Allow microphone access in your browser settings."
        : `Voice input error: ${event.error || "please try again"}.`);
      recognition.onend = () => setListening(false);
      recognitionRef.current = recognition;
      recognition.start();
      setListening(true);
    } catch {
      setListening(false);
      setVoiceError("Could not start the microphone. Check browser permission and try again.");
    }
  };

  const stopListening = () => {
    try { recognitionRef.current?.stop(); } catch { /* no active session */ }
    setListening(false);
  };

  const cleanTextForSpeech = (text) => {
    if (!text) return "";
    return String(text)
      .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
      .replace(/#+\s*/g, "")
      .replace(/[*_~`]+/g, "")
      .replace(/[•\u2022]/g, " ")
      .replace(/^\s*[-*]\s+/gm, "")
      .replace(/!{2,}/g, "!")
      .replace(/\b([01]?\d|2[0-3]):([0-5]\d)(?!\s*(?:am|pm)\b)/gi, (_, hStr, mStr) => {
        const h = parseInt(hStr, 10);
        const ampm = h >= 12 ? "PM" : "AM";
        const h12 = h % 12 || 12;
        return `${h12}:${mStr} ${ampm}`;
      })
      .replace(/\bRs\.?\s*(\d+)/gi, "$1 rupees")
      .replace(/\s+/g, " ")
      .trim();
  };

  const speak = () => {
    setVoiceError("");
    if (!canSpeak) {
      setVoiceError("Voice playback is not supported in this browser.");
      return;
    }
    const cleaned = cleanTextForSpeech(speechText);
    if (!cleaned) {
      setVoiceError("Send a message first; the assistant response will be available to play here.");
      return;
    }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(cleaned);
    utterance.lang = navigator.language || "en-US";
    window.speechSynthesis.speak(utterance);
  };

  return <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginTop: 8 }}>
    <button type="button" className="ad-btn ad-btn-ghost" disabled={disabled} onClick={listening ? stopListening : startListening} aria-pressed={listening}>
      {listening ? "■ Stop recording" : "🎙 Speak"}
    </button>
    <button type="button" className="ad-btn ad-btn-ghost" disabled={disabled || !speechText?.trim()} onClick={speak}>🔊 Play assistant reply</button>
    {voiceError && <small role="status" style={{ color: "#b91c1c", flexBasis: "100%" }}>{voiceError}</small>}
  </div>;
}
