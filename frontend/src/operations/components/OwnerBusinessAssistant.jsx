import React, { useState, useRef, useEffect } from "react";
import { operationsApi } from "../../api/operationsApi";
import { errorText } from "../../api/axiosClient";

const QUICK_PROMPTS = [
  { label: "👥 Kitne employees hain?", query: "Kitne employees hain aur unke roles kya hain?" },
  { label: "📊 Aaj ki sales & orders?", query: "Aaj ki total sales aur orders ki summary batao." },
  { label: "🛵 Pending deliveries & riders?", query: "Pending delivery orders kitne hain aur riders ka kya status hai?" },
  { label: "📦 Low stock items?", query: "Kaunse items out of stock ya low stock par hain?" },
  { label: "💳 AI usage & billing?", query: "Hamara monthly AI voice message usage aur limit kitni hai?" },
  { label: "⏸️ Pause / Resume Customer AI", query: "Customer AI agent ka status kya hai? Isse pause ya resume kaise karun?" },
];

export default function OwnerBusinessAssistant({ isDrawer = false, onClose = null }) {
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content:
        "Assalam-o-Alaikum! Main aapka **Rides AI Business Manager** hoon. Tap the microphone below and ask me anything about your employees, daily sales, rider deliveries, or inventory in English, Urdu, or Roman Urdu!",
      tools: [],
      audio_base64: null,
    },
  ]);
  const [loading, setLoading] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [wantVoiceReply, setWantVoiceReply] = useState(true);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [error, setError] = useState("");
  const [playingAudioIndex, setPlayingAudioIndex] = useState(null);

  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const recordingTimerRef = useRef(null);
  const messagesEndRef = useRef(null);
  const currentAudioElementRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading, isRecording]);

  // Clean up audio & recording on unmount
  useEffect(() => {
    return () => {
      if (recordingTimerRef.current) clearInterval(recordingTimerRef.current);
      if (currentAudioElementRef.current) {
        currentAudioElementRef.current.pause();
        currentAudioElementRef.current = null;
      }
    };
  }, []);

  const sendQuery = async (queryText, audioB64 = null) => {
    const text = (queryText || "").trim();
    if (!text && !audioB64) return;

    setError("");
    setLoading(true);

    const userMessage = {
      role: "user",
      content: text || "🎙️ Spoken Voice Note",
    };

    const nextMessages = [...messages, userMessage];
    setMessages(nextMessages);

    try {
      const historyPayload = nextMessages.slice(-8).map((m) => ({
        role: m.role,
        content: m.content,
      }));

      const res = await operationsApi.ownerAssistant({
        message: text,
        audio_base64: audioB64,
        history: historyPayload,
        want_voice_reply: wantVoiceReply,
      });

      const data = res.data;
      const assistantMessage = {
        role: "assistant",
        content: data.reply || "No response received.",
        tools: data.tools_used || [],
        audio_base64: data.audio_base64 || null,
        transcript: data.transcript,
      };

      // If user sent voice, update user's bubble text with transcribed text
      if (audioB64 && data.transcript) {
        userMessage.content = `🎙️ "${data.transcript}"`;
      }

      setMessages([...nextMessages, assistantMessage]);

      // Auto-play voice reply if available and voice replies are enabled
      if (data.audio_base64 && wantVoiceReply) {
        playAudio(data.audio_base64, nextMessages.length);
      }
    } catch (err) {
      console.error("Owner Assistant error:", err);
      let rawErr = errorText(err) || "";
      // Prevent raw HTML error dump if backend returns 404/500 HTML
      if (
        !rawErr ||
        rawErr.includes("<!DOCTYPE") ||
        rawErr.includes("<html") ||
        rawErr.includes("<head") ||
        rawErr.includes("<body") ||
        rawErr.includes("Traceback") ||
        rawErr.length > 200
      ) {
        rawErr = "Assistant endpoint unavailable. Please ensure the backend server is restarted.";
      }
      setError(rawErr);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: rawErr,
          tools: [],
          audio_base64: null,
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const startVoiceRecording = async () => {
    setError("");
    if (!navigator.mediaDevices?.getUserMedia) {
      setError("Microphone access is not supported by your browser.");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioChunksRef.current = [];
      const mimeType = MediaRecorder.isTypeSupported("audio/webm")
        ? "audio/webm"
        : MediaRecorder.isTypeSupported("audio/mp4")
        ? "audio/mp4"
        : "";

      const options = mimeType ? { mimeType } : {};
      const recorder = new MediaRecorder(stream, options);
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) {
          audioChunksRef.current.push(e.data);
        }
      };

      recorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop());
        if (recordingTimerRef.current) clearInterval(recordingTimerRef.current);
        setRecordingSeconds(0);
        setIsRecording(false);

        const audioBlob = new Blob(audioChunksRef.current, {
          type: mimeType || "audio/webm",
        });
        if (audioBlob.size < 100) return;

        const reader = new FileReader();
        reader.onloadend = () => {
          const base64Audio = reader.result;
          sendQuery("", base64Audio);
        };
        reader.readAsDataURL(audioBlob);
      };

      recorder.start(250);
      setIsRecording(true);
      setRecordingSeconds(0);
      recordingTimerRef.current = setInterval(() => {
        setRecordingSeconds((prev) => prev + 1);
      }, 1000);
    } catch (err) {
      console.error("Microphone permission error:", err);
      setError("Please allow microphone permissions to speak to your Business Manager.");
      setIsRecording(false);
    }
  };

  const stopVoiceRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
      mediaRecorderRef.current.stop();
    }
  };

  const playAudio = (audioBase64, index) => {
    if (!audioBase64) return;

    if (currentAudioElementRef.current) {
      currentAudioElementRef.current.pause();
      currentAudioElementRef.current = null;
    }

    if (playingAudioIndex === index) {
      setPlayingAudioIndex(null);
      return;
    }

    try {
      const audio = new Audio(audioBase64);
      currentAudioElementRef.current = audio;
      setPlayingAudioIndex(index);

      audio.onended = () => {
        setPlayingAudioIndex(null);
        currentAudioElementRef.current = null;
      };
      audio.onerror = () => {
        setPlayingAudioIndex(null);
        currentAudioElementRef.current = null;
      };

      audio.play();
    } catch (e) {
      console.error("Failed to play audio:", e);
      setPlayingAudioIndex(null);
    }
  };

  const clearChat = () => {
    if (currentAudioElementRef.current) {
      currentAudioElementRef.current.pause();
      currentAudioElementRef.current = null;
    }
    setPlayingAudioIndex(null);
    setMessages([
      {
        role: "assistant",
        content:
          "Assalam-o-Alaikum! Conversation cleared. Tap the microphone below to ask any question.",
        tools: [],
        audio_base64: null,
      },
    ]);
  };

  const formatTimer = (sec) => {
    const m = Math.floor(sec / 60);
    const s = (sec % 60).toString().padStart(2, "0");
    return `${m}:${s}`;
  };

  const renderContent = (text) => {
    if (!text) return null;
    const lines = text.split("\n");
    return lines.map((line, idx) => {
      let trimmed = line.trim();
      const isBullet = trimmed.startsWith("•") || trimmed.startsWith("-");
      if (isBullet) trimmed = trimmed.replace(/^[•\-]\s*/, "");

      const parts = trimmed.split(/(\*\*.*?\*\*)/g);

      return (
        <div
          key={idx}
          style={{
            minHeight: line.trim() ? "auto" : 8,
            paddingLeft: isBullet ? 14 : 0,
            position: isBullet ? "relative" : "static",
            marginBottom: 3,
            lineHeight: 1.5,
          }}
        >
          {isBullet && (
            <span
              style={{
                position: "absolute",
                left: 0,
                color: "#ff77ff",
                fontWeight: 800,
              }}
            >
              •
            </span>
          )}
          {parts.map((p, pIdx) => {
            if (p.startsWith("**") && p.endsWith("**")) {
              return <strong key={pIdx}>{p.slice(2, -2)}</strong>;
            }
            return <span key={pIdx}>{p}</span>;
          })}
        </div>
      );
    });
  };

  return (
    <div
      className={`oba-root ${isDrawer ? "oba-drawer" : "oba-embedded"}`}
      style={{
        display: "flex",
        flexDirection: "column",
        background: "#ffffff",
        borderRadius: isDrawer ? "20px 0 0 20px" : 16,
        border: isDrawer ? "none" : "1px solid #f0e6f2",
        boxShadow: isDrawer
          ? "-8px 0 35px rgba(48, 25, 52, 0.15)"
          : "0 4px 20px rgba(255, 119, 255, 0.06)",
        height: isDrawer ? "100%" : 580,
        maxHeight: isDrawer ? "100vh" : 620,
        overflow: "hidden",
        position: "relative",
      }}
    >
      <style>{`
        .oba-btn-chip {
          background: #fff0ff;
          color: #a21caf;
          border: 1px solid #f5d0fe;
          border-radius: 18px;
          padding: 6px 13px;
          font-size: 12px;
          font-weight: 600;
          cursor: pointer;
          white-space: nowrap;
          transition: all 0.15s ease;
        }
        .oba-btn-chip:hover {
          background: #ff77ff;
          color: #ffffff;
          border-color: #ff77ff;
          transform: translateY(-1px);
        }
        .oba-bubble-user {
          background: #fdf2f8;
          color: #831843;
          border: 1px solid #fbcfe8;
          border-radius: 16px 16px 4px 16px;
          padding: 10px 14px;
          max-width: 82%;
          margin-left: auto;
          font-size: 13.5px;
          box-shadow: 0 2px 6px rgba(251, 207, 232, 0.3);
        }
        .oba-bubble-ai {
          background: #f8fafc;
          color: #1e293b;
          border: 1px solid #e2e8f0;
          border-radius: 16px 16px 16px 4px;
          padding: 12px 16px;
          max-width: 88%;
          margin-right: auto;
          font-size: 13.5px;
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.03);
        }
        .oba-mic-pulse {
          animation: obaPulse 1.4s infinite;
        }
        @keyframes obaPulse {
          0% { box-shadow: 0 0 0 0 rgba(255, 119, 255, 0.7); }
          70% { box-shadow: 0 0 0 16px rgba(255, 119, 255, 0); }
          100% { box-shadow: 0 0 0 0 rgba(255, 119, 255, 0); }
        }
        .oba-recording-pulse {
          animation: obaRecPulse 1.2s infinite;
        }
        @keyframes obaRecPulse {
          0% { box-shadow: 0 0 0 0 rgba(225, 29, 72, 0.8); }
          70% { box-shadow: 0 0 0 18px rgba(225, 29, 72, 0); }
          100% { box-shadow: 0 0 0 0 rgba(225, 29, 72, 0); }
        }
      `}</style>

      {/* Top Header */}
      <div
        style={{
          padding: "14px 18px",
          background: "linear-gradient(135deg, #fdf4ff 0%, #fae8ff 100%)",
          borderBottom: "1px solid #f0abfc",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: 10,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div
            style={{
              width: 38,
              height: 38,
              borderRadius: 12,
              background: "#ff77ff",
              display: "grid",
              placeItems: "center",
              fontSize: 20,
              boxShadow: "0 3px 10px rgba(255, 119, 255, 0.35)",
            }}
          >
            🎙️
          </div>
          <div>
            <h3 style={{ margin: 0, fontSize: 15.5, fontWeight: 800, color: "#86198f" }}>
              AI Business Manager (100% Voice-Only)
            </h3>
            <div style={{ fontSize: 11.5, color: "#a21caf", fontWeight: 600 }}>
              Owner Executive Voice Copilot • English / Urdu / Roman Urdu
            </div>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <label
            title="Spoken voice replies (TTS) auto-play"
            style={{
              display: "flex",
              alignItems: "center",
              gap: 5,
              fontSize: 12,
              color: "#86198f",
              fontWeight: 650,
              cursor: "pointer",
              background: "#ffffff",
              padding: "4px 8px",
              borderRadius: 8,
              border: "1px solid #f5d0fe",
            }}
          >
            <input
              type="checkbox"
              checked={wantVoiceReply}
              onChange={(e) => setWantVoiceReply(e.target.checked)}
              style={{ accentColor: "#ff77ff", cursor: "pointer" }}
            />
            🔊 Voice
          </label>

          <button
            onClick={clearChat}
            title="Clear Chat History"
            style={{
              background: "#ffffff",
              border: "1px solid #f5d0fe",
              color: "#a21caf",
              padding: "4px 8px",
              borderRadius: 8,
              fontSize: 12,
              fontWeight: 650,
              cursor: "pointer",
            }}
          >
            Clear
          </button>

          {isDrawer && onClose && (
            <button
              onClick={onClose}
              title="Close Drawer"
              style={{
                background: "#f1f5f9",
                border: "none",
                borderRadius: 8,
                width: 28,
                height: 28,
                display: "grid",
                placeItems: "center",
                fontSize: 16,
                color: "#64748b",
                cursor: "pointer",
              }}
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {/* Quick Voice Hints / Question Chips Bar */}
      <div
        style={{
          padding: "8px 14px",
          background: "#faf5ff",
          borderBottom: "1px solid #f3e8ff",
          display: "flex",
          gap: 6,
          overflowX: "auto",
          whiteSpace: "nowrap",
        }}
      >
        {QUICK_PROMPTS.map((p, idx) => (
          <button
            key={idx}
            className="oba-btn-chip"
            disabled={loading || isRecording}
            onClick={() => sendQuery(p.query)}
            title={`Ask voice question: "${p.query}"`}
          >
            {p.label}
          </button>
        ))}
      </div>

      {error && (
        <div
          style={{
            background: "#fef2f2",
            color: "#991b1b",
            fontSize: 12,
            padding: "8px 14px",
            borderBottom: "1px solid #fecaca",
          }}
        >
          {error}
        </div>
      )}

      {/* Messages Scroll Area */}
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          padding: 16,
          display: "flex",
          flexDirection: "column",
          gap: 12,
          background: "#ffffff",
        }}
      >
        {messages.map((m, idx) => (
          <div key={idx} style={{ display: "flex", flexDirection: "column" }}>
            <div className={m.role === "user" ? "oba-bubble-user" : "oba-bubble-ai"}>
              {renderContent(m.content)}

              {/* Tools execution badge */}
              {m.tools && m.tools.length > 0 && (
                <div
                  style={{
                    marginTop: 8,
                    paddingTop: 6,
                    borderTop: "1px dashed #cbd5e1",
                    display: "flex",
                    gap: 6,
                    flexWrap: "wrap",
                    alignItems: "center",
                  }}
                >
                  <span style={{ fontSize: 10, color: "#64748b", fontWeight: 700 }}>
                    ⚡ Verified with live tools:
                  </span>
                  {m.tools.map((t, tIdx) => (
                    <span
                      key={tIdx}
                      style={{
                        fontSize: 10,
                        background: "#ecfdf5",
                        color: "#047857",
                        padding: "1px 6px",
                        borderRadius: 6,
                        fontWeight: 600,
                        fontFamily: "monospace",
                      }}
                    >
                      {t}
                    </span>
                  ))}
                </div>
              )}

              {/* Spoken voice replay button */}
              {m.audio_base64 && (
                <div style={{ marginTop: 8 }}>
                  <button
                    onClick={() => playAudio(m.audio_base64, idx)}
                    style={{
                      background: playingAudioIndex === idx ? "#ff77ff" : "#f1f5f9",
                      color: playingAudioIndex === idx ? "#ffffff" : "#475569",
                      border: "none",
                      borderRadius: 12,
                      padding: "4px 10px",
                      fontSize: 11.5,
                      fontWeight: 700,
                      cursor: "pointer",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 5,
                      transition: "all 0.15s ease",
                    }}
                  >
                    {playingAudioIndex === idx ? "⏸ Pause Voice" : "🔊 Replay Voice"}
                  </button>
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="oba-bubble-ai" style={{ width: "fit-content" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, color: "#a21caf" }}>
              <span style={{ fontSize: 16 }}>🎙️</span>
              <span style={{ fontSize: 13, fontWeight: 600 }}>Processing speech & checking business records...</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* 100% Voice-Only Bottom Control Bar (No Text Input / No Send Button) */}
      <div
        style={{
          padding: "16px 20px",
          background: "linear-gradient(180deg, #faf5ff 0%, #fdf4ff 100%)",
          borderTop: "1px solid #f0abfc",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: 8,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <button
            type="button"
            disabled={loading}
            onClick={isRecording ? stopVoiceRecording : startVoiceRecording}
            title={isRecording ? "Tap to Stop & Process Audio" : "Tap to Speak (Voice Only)"}
            style={{
              padding: isRecording ? "12px 24px" : "12px 26px",
              borderRadius: 30,
              border: "none",
              background: isRecording
                ? "linear-gradient(135deg, #e11d48 0%, #be123c 100%)"
                : "linear-gradient(135deg, #ff77ff 0%, #f05cf0 100%)",
              color: "#ffffff",
              fontSize: 15,
              fontWeight: 800,
              cursor: loading ? "wait" : "pointer",
              display: "flex",
              alignItems: "center",
              gap: 9,
              boxShadow: isRecording
                ? "0 4px 18px rgba(225, 29, 72, 0.45)"
                : "0 4px 18px rgba(255, 119, 255, 0.4)",
              transition: "all 0.2s ease",
            }}
            className={isRecording ? "oba-recording-pulse" : ""}
          >
            {isRecording ? (
              <>
                <span style={{ fontSize: 18 }}>⏹</span>
                <span>Stop & Send (🔴 {formatTimer(recordingSeconds)})</span>
              </>
            ) : (
              <>
                <span style={{ fontSize: 19 }}>🎙️</span>
                <span>{loading ? "Processing..." : "Tap to Speak (Voice Only)"}</span>
              </>
            )}
          </button>
        </div>

        <div style={{ fontSize: 11.5, color: "#9333ea", fontWeight: 600 }}>
          {isRecording
            ? "🔴 Recording active... Speak in English, Urdu, or Roman Urdu, then tap to stop."
            : "100% Voice-First Copilot • Tap mic to speak or click any question chip above"}
        </div>
      </div>
    </div>
  );
}
