import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import api from "../api/axiosClient";

export default function PublicAgentPage() {
  const { publicId } = useParams();

  // Tenant / Business Info
  const [businessName, setBusinessName] = useState("Business Assistant");
  const [businessType, setBusinessType] = useState("restaurant");
  const [catalog, setCatalog] = useState([]);
  const [serviceAreas, setServiceAreas] = useState([]);

  // Customer contact info (optional / for orders)
  const [customer, setCustomer] = useState({ name: "", email: "", phone: "" });
  const [showContactModal, setShowContactModal] = useState(false);

  // Conversation & Read-only Display State
  const isEmbed = typeof window !== "undefined" && new URLSearchParams(window.location.search).get("embed") === "1";
  const storageKey = `ridesai_public_conv_${publicId}`;
  const [conversationId, setConversationId] = useState(null);
  const conversationIdRef = useRef(null);
  const [messages, setMessages] = useState([]);
  const [hydratingChat, setHydratingChat] = useState(false);
  const [error, setError] = useState("");
  const [monthlyLimitReached, setMonthlyLimitReached] = useState(false);
  const [aiPaused, setAiPaused] = useState(false);

  // Voice Interaction State: "idle" | "listening" | "processing" | "speaking"
  const [voiceState, setVoiceState] = useState("idle");
  const [interimTranscript, setInterimTranscript] = useState("");
  const [recordingSeconds, setRecordingSeconds] = useState(0);

  // Audio & Speech refs
  const recognitionRef = useRef(null);
  const currentAudioRef = useRef(null);
  const mediaStreamRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const isRecordingRef = useRef(false);
  const recordingTimerRef = useRef(null);
  const transcriptBufferRef = useRef("");
  const messagesEndRef = useRef(null);

  const SpeechRecognition =
    typeof window !== "undefined"
      ? window.SpeechRecognition || window.webkitSpeechRecognition
      : null;
  const canSynthesize = typeof window !== "undefined" && "speechSynthesis" in window;

  const formatTimer = (secs) => {
    const mins = Math.floor(secs / 60);
    const remainder = secs % 60;
    return `${mins}:${remainder < 10 ? "0" : ""}${remainder}`;
  };

  // Auto-scroll transcript feed to bottom
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, interimTranscript, voiceState]);

  // Load business catalog, info, and hydrate any saved conversation from localStorage
  useEffect(() => {
    let cancelled = false;
    api
      .get(`/operations/public/agent/${publicId}/catalog/`)
      .then(({ data }) => {
        if (cancelled) return;
        setCatalog(data.items || []);
        setServiceAreas(data.service_areas || []);
        if (data.business) setBusinessName(data.business);
        if (data.ai_paused) {
          setAiPaused(true);
        }
        if (data.monthly_limit_reached) {
          setMonthlyLimitReached(true);
          setError("This business's AI Voice Agent has reached its monthly usage limit. Please contact the business directly.");
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err.response?.data?.detail || "This business assistant is currently unavailable.");
        }
      });

    // Hydrate saved conversation on mount / page reload (sessionStorage clears automatically on tab close)
    let savedConvId = null;
    try {
      savedConvId = window.sessionStorage.getItem(storageKey);
    } catch {
      savedConvId = null;
    }

    if (savedConvId) {
      conversationIdRef.current = savedConvId;
      setConversationId(savedConvId);
      setHydratingChat(true);
      api
        .get(`/operations/public/agent/${publicId}/conversation/${savedConvId}/`)
        .then(({ data }) => {
          if (cancelled) return;
          const hydrated = (data?.messages || []).map((m) => ({
            role: m.role,
            content: m.content,
            is_voice: Boolean(m.metadata?.is_voice),
            audio_url: m.metadata?.audio_url || null,
            menu_items: m.metadata?.menu_items || [],
            order_summary: m.metadata?.order_summary || null,
          }));
          if (hydrated.length > 0) {
            setMessages(hydrated);
          }
        })
        .catch((err) => {
          if (cancelled) return;
          // Clear stale/invalid conversation ID on 404/400 so the user can start fresh cleanly
          if (err?.response?.status === 404 || err?.response?.status === 400) {
            try {
              window.sessionStorage.removeItem(storageKey);
            } catch {}
            conversationIdRef.current = null;
            setConversationId(null);
          }
        })
        .finally(() => {
          if (!cancelled) setHydratingChat(false);
        });
    } else {
      conversationIdRef.current = null;
      setConversationId(null);
      setMessages([]);
    }

    return () => {
      cancelled = true;
      stopAllAudio();
      stopAllRecording();
    };
  }, [publicId, storageKey]);

  // Clear saved conversation and start a fresh voice session
  const handleNewChat = () => {
    stopAllAudio();
    stopAllRecording();
    try {
      window.sessionStorage.removeItem(storageKey);
    } catch {}
    conversationIdRef.current = null;
    setConversationId(null);
    setMessages([]);
    setError("");
    setInterimTranscript("");
    setRecordingSeconds(0);
    setVoiceState("idle");
  };

  const stopAllAudio = () => {
    if (currentAudioRef.current) {
      currentAudioRef.current.pause();
      currentAudioRef.current = null;
    }
    if (canSynthesize) {
      window.speechSynthesis.cancel();
    }
  };

  // Play audio response (TTS audio_url or browser SpeechSynthesis fallback)
  const playVoiceResponse = (audioUrl, text) => {
    stopAllAudio();
    setVoiceState("speaking");

    if (audioUrl) {
      const audio = new Audio(audioUrl);
      currentAudioRef.current = audio;
      audio.onended = () => {
        setVoiceState("idle");
        currentAudioRef.current = null;
      };
      audio.onerror = () => {
        // Fallback to browser SpeechSynthesis if audio element fails
        fallbackSpeak(text);
      };
      audio.play().catch(() => {
        fallbackSpeak(text);
      });
    } else {
      fallbackSpeak(text);
    }
  };

  const fallbackSpeak = (text) => {
    if (!canSynthesize || !text) {
      setVoiceState("idle");
      return;
    }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "en-US";
    utterance.rate = 0.95;
    utterance.onend = () => setVoiceState("idle");
    utterance.onerror = () => setVoiceState("idle");
    window.speechSynthesis.speak(utterance);
  };

  // Send spoken voice payload to backend
  const sendVoiceMessage = async (spokenText, audioBase64 = null) => {
    if (!spokenText?.trim() && !audioBase64) {
      setVoiceState("idle");
      return;
    }

    const optimisticText = spokenText?.trim() || "🎤 Processing voice note...";
    // Append customer spoken message to read-only feed
    setMessages((prev) => [...prev, { role: "user", content: optimisticText, is_voice: true }]);
    setVoiceState("processing");
    setError("");
    setInterimTranscript("");

    try {
      const activeConvId = conversationIdRef.current || conversationId;
      const { data } = await api.post(`/operations/public/agent/${publicId}/chat/`, {
        message: spokenText?.trim() || "",
        audio_base64: audioBase64,
        audio: audioBase64,
        conversation_id: activeConvId,
        customer_name: customer.name,
        customer_email: customer.email,
        customer_phone: customer.phone,
      });

      if (data?.conversation_id) {
        conversationIdRef.current = data.conversation_id;
        setConversationId(data.conversation_id);
        try {
          window.sessionStorage.setItem(storageKey, data.conversation_id);
        } catch {}
      }
      const reply = data.reply_text || data.answer || "";
      const actualTranscript = data.transcript || optimisticText;

      // Update the optimistic customer message with Whisper's full transcript
      setMessages((prev) => {
        const next = [...prev];
        for (let i = next.length - 1; i >= 0; i--) {
          if (next[i].role === "user") {
            next[i] = { ...next[i], content: actualTranscript };
            break;
          }
        }
        next.push({
          role: "assistant",
          content: reply,
          audio_url: data.audio_url || null,
          menu_items: data.menu_items || [],
          order_summary: data.order_summary || null,
          action_result: data.action_result || null,
        });
        return next;
      });

      // Auto-play voice reply
      playVoiceResponse(data.audio_url, reply);
    } catch (err) {
      const errData = err.response?.data;
      if (
        err.response?.status === 402 ||
        errData?.error === "monthly_limit_reached" ||
        errData?.error === "subscription_inactive"
      ) {
        setMonthlyLimitReached(true);
        setError(
          errData?.message ||
            errData?.detail ||
            "This business's AI Voice Agent has reached its monthly usage limit. Please contact the business directly."
        );
      } else if (
        err.response?.status === 403 &&
        (errData?.error === "ai_paused" || (typeof errData?.detail === "string" && errData.detail.includes("paused")))
      ) {
        setAiPaused(true);
        setError(errData?.message || errData?.detail || "AI Voice Agent has been paused by the business owner.");
      } else {
        setError(errData?.detail || errData?.message || "Voice processing failed. Please try speaking again.");
      }
      setVoiceState("idle");
    }
  };

  // Start Voice Recording (MediaRecorder as PRIMARY capture)
  const startListening = async () => {
    setError("");
    stopAllAudio();
    transcriptBufferRef.current = "";
    audioChunksRef.current = [];
    setInterimTranscript("");
    setRecordingSeconds(0);

    // 1. Primary: MediaRecorder with manual tap-to-start / tap-to-stop
    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        throw new Error("Microphone access is not supported in this browser.");
      }

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaStreamRef.current = stream;

      let mimeType = "";
      if (typeof MediaRecorder !== "undefined") {
        if (MediaRecorder.isTypeSupported("audio/webm;codecs=opus")) {
          mimeType = "audio/webm;codecs=opus";
        } else if (MediaRecorder.isTypeSupported("audio/webm")) {
          mimeType = "audio/webm";
        } else if (MediaRecorder.isTypeSupported("audio/mp4")) {
          mimeType = "audio/mp4";
        }
      }

      const options = mimeType ? { mimeType } : undefined;
      const mediaRecorder = new MediaRecorder(stream, options);
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.start(200); // 200ms slice interval
      isRecordingRef.current = true;
      setVoiceState("listening");

      // Start live timer
      if (recordingTimerRef.current) clearInterval(recordingTimerRef.current);
      recordingTimerRef.current = setInterval(() => {
        setRecordingSeconds((prev) => prev + 1);
      }, 1000);
    } catch (micErr) {
      console.error("Microphone capture error:", micErr);
      setError("Microphone permission was denied or not available. Please allow microphone access and tap again.");
      setVoiceState("idle");
      return;
    }

    // 2. Optional Browser SpeechRecognition for live visual interim text feedback only
    // Crucial: continuous=true and onend DOES NOT stop recording or send!
    if (SpeechRecognition) {
      try {
        const recognition = new SpeechRecognition();
        recognition.lang = navigator.language || "en-US";
        recognition.interimResults = true;
        recognition.continuous = true;
        recognition.maxAlternatives = 1;

        recognition.onresult = (event) => {
          let interim = "";
          let final = "";
          for (let i = event.resultIndex; i < event.results.length; ++i) {
            const trans = event.results[i][0].transcript;
            if (event.results[i].isFinal) {
              final += trans;
            } else {
              interim += trans;
            }
          }
          if (final) {
            transcriptBufferRef.current = (transcriptBufferRef.current + " " + final).trim();
            setInterimTranscript(transcriptBufferRef.current);
          } else {
            setInterimTranscript((transcriptBufferRef.current + " " + interim).trim());
          }
        };

        recognition.onerror = (event) => {
          console.warn("SpeechRecognition interim note:", event.error);
        };

        recognition.onend = () => {
          // If browser speech recognition cuts out on silence, NEVER stop recording!
          // Auto-restart recognition if still recording, so user keeps seeing live text
          if (isRecordingRef.current) {
            try {
              recognition.start();
            } catch {
              /* ignore restart error */
            }
          }
        };

        recognitionRef.current = recognition;
        try {
          recognition.start();
        } catch {
          /* ignore recognition start error */
        }
      } catch (err) {
        console.warn("SpeechRecognition initialization note:", err);
      }
    }
  };

  // Stop recording and send audio to backend Whisper
  const stopListeningAndSend = () => {
    isRecordingRef.current = false;
    if (recordingTimerRef.current) {
      clearInterval(recordingTimerRef.current);
      recordingTimerRef.current = null;
    }

    // Stop live SpeechRecognition
    if (recognitionRef.current) {
      try {
        recognitionRef.current.onend = null;
        recognitionRef.current.stop();
      } catch {
        /* already stopped */
      }
      recognitionRef.current = null;
    }

    const currentRecorder = mediaRecorderRef.current;
    if (currentRecorder && currentRecorder.state !== "inactive") {
      setVoiceState("processing");

      currentRecorder.onstop = () => {
        try {
          const mimeType = currentRecorder.mimeType || "audio/webm";
          const audioBlob = new Blob(audioChunksRef.current, { type: mimeType });

          // Release mic hardware tracks
          if (mediaStreamRef.current) {
            mediaStreamRef.current.getTracks().forEach((track) => track.stop());
            mediaStreamRef.current = null;
          }

          const spokenHint = transcriptBufferRef.current.trim() || interimTranscript.trim();

          if (audioBlob.size > 100) {
            const reader = new FileReader();
            reader.readAsDataURL(audioBlob);
            reader.onloadend = () => {
              const base64Data = reader.result;
              sendVoiceMessage(spokenHint, base64Data);
            };
          } else {
            if (spokenHint) {
              sendVoiceMessage(spokenHint, null);
            } else {
              setVoiceState("idle");
              setInterimTranscript("");
            }
          }
        } catch (blobErr) {
          console.error("Audio blob processing error:", blobErr);
          const spokenHint = transcriptBufferRef.current.trim() || interimTranscript.trim();
          if (spokenHint) {
            sendVoiceMessage(spokenHint, null);
          } else {
            setVoiceState("idle");
          }
        }
      };

      try {
        currentRecorder.stop();
      } catch (err) {
        console.error("Error stopping recorder:", err);
        setVoiceState("idle");
      }
    } else {
      // Fallback if no media recorder was active
      if (mediaStreamRef.current) {
        mediaStreamRef.current.getTracks().forEach((track) => track.stop());
        mediaStreamRef.current = null;
      }
      const spokenHint = transcriptBufferRef.current.trim() || interimTranscript.trim();
      if (spokenHint) {
        sendVoiceMessage(spokenHint, null);
      } else {
        setVoiceState("idle");
        setInterimTranscript("");
      }
    }
  };

  const stopAllRecording = () => {
    isRecordingRef.current = false;
    if (recordingTimerRef.current) {
      clearInterval(recordingTimerRef.current);
      recordingTimerRef.current = null;
    }
    if (recognitionRef.current) {
      try {
        recognitionRef.current.onend = null;
        recognitionRef.current.stop();
      } catch {}
      recognitionRef.current = null;
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      try {
        mediaRecorderRef.current.onstop = null;
        mediaRecorderRef.current.stop();
      } catch {}
      mediaRecorderRef.current = null;
    }
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((t) => t.stop());
      mediaStreamRef.current = null;
    }
  };

  // Main Action: Toggle Mic Button
  const handleMicClick = () => {
    if (monthlyLimitReached) return;
    if (voiceState === "speaking") {
      // Mute / stop talking
      stopAllAudio();
      setVoiceState("idle");
    } else if (voiceState === "listening") {
      // Customer tapped again to finish speaking and send uncut audio!
      stopListeningAndSend();
    } else if (voiceState === "idle") {
      // Start recording
      startListening();
    }
  };

  return (
    <main
      style={{
        minHeight: isEmbed ? "100%" : "100vh",
        background: isEmbed ? "#ffffff" : "linear-gradient(180deg, #fdf4ff 0%, #f8fafc 100%)",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "space-between",
        padding: isEmbed ? "8px" : "16px",
        fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
      }}
    >
      <style>{`
        @keyframes pulseRing {
          0% {
            box-shadow: 0 0 0 0 rgba(255, 119, 255, 0.7);
          }
          70% {
            box-shadow: 0 0 0 26px rgba(255, 119, 255, 0);
          }
          100% {
            box-shadow: 0 0 0 0 rgba(255, 119, 255, 0);
          }
        }
        @keyframes waveBars {
          0%, 100% { height: 6px; }
          50% { height: 26px; }
        }
        .voice-mic-active {
          animation: pulseRing 1.8s infinite;
        }
        .wave-bar {
          width: 4px;
          background: #ff77ff;
          border-radius: 2px;
          display: inline-block;
          animation: waveBars 1s infinite ease-in-out;
        }
        .wave-bar:nth-child(2) { animation-delay: 0.15s; }
        .wave-bar:nth-child(3) { animation-delay: 0.3s; }
        .wave-bar:nth-child(4) { animation-delay: 0.45s; }
        .wave-bar:nth-child(5) { animation-delay: 0.6s; }
      `}</style>

      {/* Container Box */}
      <div
        style={{
          width: "100%",
          maxWidth: "680px",
          display: "flex",
          flexDirection: "column",
          gap: isEmbed ? "8px" : "14px",
          margin: "0 auto",
        }}
      >
        {/* Top Header Card with Mandatory Branding */}
        <header
          style={{
            background: "#ffffff",
            border: "1px solid #f0abfc",
            borderRadius: isEmbed ? "14px" : "20px",
            padding: isEmbed ? "10px 14px" : "18px 22px",
            boxShadow: "0 10px 25px -5px rgba(255, 119, 255, 0.12)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexWrap: "wrap",
            gap: "8px",
          }}
        >
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <span
                style={{
                  fontSize: "10px",
                  fontWeight: "700",
                  textTransform: "uppercase",
                  letterSpacing: "0.08em",
                  background: "#fae8ff",
                  color: "#c026d3",
                  padding: "3px 8px",
                  borderRadius: "12px",
                }}
              >
                100% Voice AI
              </span>
              <span style={{ fontSize: "12px", color: "#64748b" }}>Live Customer Line</span>
            </div>
            {/* Prominent Business Name */}
            <h1
              style={{
                fontSize: isEmbed ? "18px" : "24px",
                fontWeight: "800",
                color: "#0f172a",
                margin: "4px 0 2px 0",
              }}
            >
              {businessName}
            </h1>
            {/* Mandatory Subtitle Branding */}
            <p
              style={{
                fontSize: isEmbed ? "11px" : "12px",
                fontWeight: "600",
                color: "#a855f7",
                margin: 0,
                letterSpacing: "0.02em",
              }}
            >
              Owned by Rides Technologies
            </p>
          </div>

          {/* Header Action Buttons: New Chat & Customer Details */}
          <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
            <button
              type="button"
              onClick={handleNewChat}
              disabled={voiceState === "processing" || hydratingChat}
              title="Start a fresh voice chat session"
              style={{
                background: "#ffffff",
                border: "1px solid #f0abfc",
                borderRadius: "14px",
                padding: isEmbed ? "6px 10px" : "8px 13px",
                fontSize: isEmbed ? "11px" : "12px",
                fontWeight: "600",
                color: "#a21caf",
                cursor: voiceState === "processing" || hydratingChat ? "not-allowed" : "pointer",
                display: "flex",
                alignItems: "center",
                gap: "5px",
                opacity: voiceState === "processing" || hydratingChat ? 0.6 : 1,
              }}
            >
              <span>✨</span>
              <span>New Chat</span>
            </button>

            <button
              type="button"
              onClick={() => setShowContactModal(true)}
              style={{
                background: "#faf5ff",
                border: "1px solid #e9d5ff",
                borderRadius: "14px",
                padding: isEmbed ? "6px 10px" : "8px 14px",
                fontSize: isEmbed ? "11px" : "12px",
                fontWeight: "600",
                color: "#7e22ce",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: "6px",
              }}
            >
              <span>👤</span>
              <span>{customer.name || customer.phone ? `${customer.name || customer.phone}` : "Add Details"}</span>
            </button>
          </div>
        </header>

        {/* Read-Only Transcript & Cards Feed */}
        <section
          aria-live="polite"
          style={{
            background: "#ffffff",
            border: "1px solid #e2e8f0",
            borderRadius: isEmbed ? "14px" : "20px",
            height: isEmbed ? "calc(100vh - 230px)" : "50vh",
            minHeight: isEmbed ? "240px" : "360px",
            overflowY: "auto",
            padding: isEmbed ? "12px" : "18px",
            display: "flex",
            flexDirection: "column",
            gap: isEmbed ? "10px" : "16px",
            boxShadow: "0 4px 18px rgba(15, 23, 42, 0.04)",
          }}
        >
          {messages.length === 0 ? (
            <div
              style={{
                margin: "auto",
                textAlign: "center",
                padding: "24px 12px",
                maxWidth: "420px",
              }}
            >
              <div
                style={{
                  width: "56px",
                  height: "56px",
                  borderRadius: "28px",
                  background: "#fae8ff",
                  display: "grid",
                  placeItems: "center",
                  fontSize: "26px",
                  margin: "0 auto 12px auto",
                }}
              >
                🎙️
              </div>
              <h3 style={{ margin: "0 0 6px 0", color: "#1e293b", fontSize: "18px", fontWeight: "700" }}>
                Welcome to {businessName}
              </h3>
              <p style={{ margin: "0 0 16px 0", color: "#64748b", fontSize: "14px", lineHeight: 1.5 }}>
                Tap the microphone below to speak directly with our AI assistant. You can ask about our menu, prices, doctor timings, or place an order.
              </p>
              <div style={{ display: "flex", flexDirection: "column", gap: "8px", alignItems: "center" }}>
                <span style={{ fontSize: "12px", fontWeight: "600", color: "#a855f7" }}>Try saying:</span>
                <span
                  style={{
                    background: "#f8fafc",
                    border: "1px dashed #cbd5e1",
                    padding: "6px 14px",
                    borderRadius: "16px",
                    fontSize: "12px",
                    color: "#475569",
                  }}
                >
                  "What is on the menu today?"
                </span>
                <span
                  style={{
                    background: "#f8fafc",
                    border: "1px dashed #cbd5e1",
                    padding: "6px 14px",
                    borderRadius: "16px",
                    fontSize: "12px",
                    color: "#475569",
                  }}
                >
                  "I want to place an order for delivery"
                </span>
              </div>
            </div>
          ) : (
            messages.map((m, idx) => (
              <div
                key={idx}
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: m.role === "user" ? "flex-end" : "flex-start",
                  gap: "6px",
                }}
              >
                {/* Speaker Label */}
                <span
                  style={{
                    fontSize: "11px",
                    fontWeight: "700",
                    color: m.role === "user" ? "#a855f7" : "#64748b",
                    textTransform: "uppercase",
                    letterSpacing: "0.04em",
                    display: "flex",
                    alignItems: "center",
                    gap: "4px",
                  }}
                >
                  {m.role === "user" ? "🎤 You (Spoken)" : "🤖 Assistant (Voice)"}
                </span>

                {/* Spoken Text Bubble */}
                <div
                  style={{
                    maxWidth: "88%",
                    padding: "12px 16px",
                    borderRadius: m.role === "user" ? "18px 18px 4px 18px" : "18px 18px 18px 4px",
                    background: m.role === "user" ? "#fae8ff" : "#f8fafc",
                    border: m.role === "user" ? "1px solid #f5d0fe" : "1px solid #e2e8f0",
                    color: "#0f172a",
                    fontSize: "14px",
                    lineHeight: "1.55",
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-word",
                  }}
                >
                  {m.content}

                  {/* Replay voice button for assistant messages */}
                  {m.role === "assistant" && (
                    <div style={{ marginTop: "8px", display: "flex", gap: "8px" }}>
                      <button
                        type="button"
                        onClick={() => playVoiceResponse(m.audio_url, m.content)}
                        style={{
                          background: "#ffffff",
                          border: "1px solid #cbd5e1",
                          borderRadius: "12px",
                          padding: "4px 10px",
                          fontSize: "11px",
                          fontWeight: "600",
                          color: "#475569",
                          cursor: "pointer",
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "4px",
                        }}
                      >
                        <span>🔊</span> Replay Voice
                      </button>
                    </div>
                  )}
                </div>

                {/* Structured Cards: Menu / Catalog Items */}
                {m.menu_items && m.menu_items.length > 0 && (
                  <div
                    style={{
                      maxWidth: "100%",
                      width: "100%",
                      marginTop: "4px",
                      display: "grid",
                      gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
                      gap: "10px",
                    }}
                  >
                    {m.menu_items.map((item) => (
                      <div
                        key={item.id}
                        style={{
                          background: "#ffffff",
                          border: "1px solid #e2e8f0",
                          borderRadius: "14px",
                          padding: "12px",
                          boxShadow: "0 2px 8px rgba(0,0,0,0.03)",
                        }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                          <strong style={{ fontSize: "14px", color: "#0f172a" }}>{item.name}</strong>
                          <span style={{ fontSize: "13px", fontWeight: "700", color: "#c026d3" }}>
                            Rs. {item.price}
                          </span>
                        </div>
                        {item.description && (
                          <p style={{ margin: "4px 0 0 0", fontSize: "11px", color: "#64748b", lineHeight: 1.4 }}>
                            {item.description}
                          </p>
                        )}
                        <div style={{ marginTop: "6px" }}>
                          <span
                            style={{
                              fontSize: "10px",
                              fontWeight: "600",
                              color: item.in_stock ? "#16a34a" : "#dc2626",
                              background: item.in_stock ? "#dcfce7" : "#fee2e2",
                              padding: "2px 6px",
                              borderRadius: "8px",
                            }}
                          >
                            {item.in_stock ? "Available" : "Out of stock"}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Structured Cards: Order / Invoice Summary */}
                {m.order_summary && (
                  <div
                    style={{
                      marginTop: "6px",
                      background: "#f0fdf4",
                      border: "1px solid #bbf7d0",
                      borderRadius: "14px",
                      padding: "12px 16px",
                      maxWidth: "88%",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "#166534", fontWeight: "700" }}>
                      <span>✅</span> Order Confirmed
                    </div>
                    <div style={{ fontSize: "13px", color: "#1e293b", marginTop: "4px" }}>
                      Order Ref: <strong>#{m.order_summary.order_number}</strong>
                    </div>
                    <div style={{ fontSize: "13px", color: "#1e293b" }}>
                      Total Amount: <strong>{String(m.order_summary.total || "").startsWith("Rs.") ? m.order_summary.total : `Rs. ${m.order_summary.total}`}</strong>
                    </div>
                  </div>
                )}
              </div>
            ))
          )}

          {/* Live speech interim feedback */}
          {voiceState === "listening" && interimTranscript && (
            <div style={{ alignSelf: "flex-end", maxWidth: "85%" }}>
              <span style={{ fontSize: "11px", fontWeight: "700", color: "#c026d3" }}>Speaking now...</span>
              <div
                style={{
                  background: "#fae8ff",
                  border: "1px dashed #d946ef",
                  borderRadius: "18px 18px 4px 18px",
                  padding: "10px 14px",
                  fontSize: "13px",
                  color: "#701a75",
                  fontStyle: "italic",
                }}
              >
                "{interimTranscript}"
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </section>

        {/* Error notification if any */}
        {error && (
          <div
            role="alert"
            style={{
              background: "#fef2f2",
              border: "1px solid #fecaca",
              borderRadius: "12px",
              padding: "10px 14px",
              color: "#991b1b",
              fontSize: "13px",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <span>{error}</span>
            <button
              type="button"
              onClick={() => setError("")}
              style={{ background: "none", border: "none", color: "#991b1b", cursor: "pointer", fontWeight: "bold" }}
            >
              ✕
            </button>
          </div>
        )}

        {/* 100% Voice Interaction Control Panel (No typing input allowed) */}
        <section
          style={{
            background: "#ffffff",
            border: "1px solid #f0abfc",
            borderRadius: isEmbed ? "18px" : "24px",
            padding: isEmbed ? "14px" : "24px",
            boxShadow: "0 12px 30px -5px rgba(255, 119, 255, 0.15)",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: "12px",
          }}
        >
          {/* AI Paused by Owner Banner */}
          {aiPaused && (
            <div
              style={{
                width: "100%",
                maxWidth: "480px",
                background: "#fffbeb",
                border: "1px solid #fde68a",
                borderRadius: "12px",
                padding: "12px 16px",
                textAlign: "center",
                color: "#92400e",
                fontSize: "13px",
                fontWeight: "600",
                boxSizing: "border-box",
              }}
            >
              ⏸️ AI Voice Agent Paused by Owner
              <p style={{ margin: "4px 0 0 0", fontSize: "12px", fontWeight: "400", color: "#b45309" }}>
                The business owner has temporarily paused AI voice assistance. Please contact the business directly.
              </p>
            </div>
          )}

          {/* Monthly Limit Reached Warning Banner */}
          {monthlyLimitReached && (
            <div
              style={{
                width: "100%",
                maxWidth: "480px",
                background: "#fef2f2",
                border: "1px solid #fecaca",
                borderRadius: "12px",
                padding: "12px 16px",
                textAlign: "center",
                color: "#991b1b",
                fontSize: "13px",
                fontWeight: "600",
                boxSizing: "border-box",
              }}
            >
              ⚠️ Monthly Voice Limit Reached
              <p style={{ margin: "4px 0 0 0", fontSize: "12px", fontWeight: "400", color: "#b91c1c" }}>
                This business has reached its monthly AI voice usage quota. Please contact the business directly.
              </p>
            </div>
          )}

          {/* Main Glowing 🎤 Voice Button */}
          <div style={{ position: "relative" }}>
            <button
              type="button"
              onClick={handleMicClick}
              disabled={voiceState === "processing" || monthlyLimitReached || aiPaused}
              aria-label={
                aiPaused
                  ? "AI Voice Agent paused by owner"
                  : monthlyLimitReached
                  ? "Monthly usage limit reached"
                  : voiceState === "listening"
                  ? "Stop recording and send"
                  : voiceState === "speaking"
                  ? "Mute audio playback"
                  : "Tap to speak"
              }
              className={voiceState === "listening" ? "voice-mic-active" : ""}
              style={{
                width: isEmbed ? "72px" : "82px",
                height: isEmbed ? "72px" : "82px",
                borderRadius: "50%",
                background:
                  aiPaused || monthlyLimitReached
                    ? "#cbd5e1"
                    : voiceState === "listening"
                    ? "linear-gradient(135deg, #d946ef 0%, #ff77ff 100%)"
                    : voiceState === "speaking"
                    ? "linear-gradient(135deg, #0284c7 0%, #38bdf8 100%)"
                    : voiceState === "processing"
                    ? "#e2e8f0"
                    : "linear-gradient(135deg, #ff77ff 0%, #ec4899 100%)",
                border: "4px solid #ffffff",
                boxShadow:
                  aiPaused || monthlyLimitReached
                    ? "none"
                    : voiceState === "listening"
                    ? "0 0 25px rgba(217, 70, 239, 0.8)"
                    : "0 10px 20px rgba(255, 119, 255, 0.35)",
                color: "#ffffff",
                fontSize: isEmbed ? "28px" : "32px",
                cursor:
                  aiPaused || monthlyLimitReached
                    ? "not-allowed"
                    : voiceState === "processing"
                    ? "wait"
                    : "pointer",
                display: "grid",
                placeItems: "center",
                transition: "all 0.25s ease",
                outline: "none",
              }}
            >
              {aiPaused ? (
                "⏸️"
              ) : monthlyLimitReached ? (
                "🔒"
              ) : voiceState === "listening" ? (
                "⏹"
              ) : voiceState === "speaking" ? (
                "🔊"
              ) : voiceState === "processing" ? (
                "⏳"
              ) : (
                "🎤"
              )}
            </button>
          </div>

          {/* Voice Status Label & Equalizer Animation */}
          <div style={{ textAlign: "center" }}>
            {aiPaused ? (
              <div>
                <strong style={{ fontSize: "16px", color: "#92400e", display: "block" }}>
                  AI Voice Agent Paused
                </strong>
                <span style={{ fontSize: "12px", color: "#78350f" }}>
                  The owner has temporarily paused AI voice assistance
                </span>
              </div>
            ) : monthlyLimitReached ? (
              <div>
                <strong style={{ fontSize: "16px", color: "#991b1b", display: "block" }}>
                  Monthly Limit Reached
                </strong>
                <span style={{ fontSize: "12px", color: "#64748b" }}>
                  Microphone is disabled until the next billing cycle
                </span>
              </div>
            ) : voiceState === "idle" ? (
              <div>
                <strong style={{ fontSize: "16px", color: "#0f172a", display: "block" }}>
                  Tap to Speak
                </strong>
                <span style={{ fontSize: "12px", color: "#64748b" }}>
                  100% voice experience · Speak naturally
                </span>
              </div>
            ) : null}

            {voiceState === "listening" && (
              <div>
                <div
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "6px",
                    background: "#fdf2f8",
                    border: "1px solid #fbcfe8",
                    padding: "3px 12px",
                    borderRadius: "20px",
                    marginBottom: "6px",
                  }}
                >
                  <span
                    style={{
                      width: "8px",
                      height: "8px",
                      borderRadius: "50%",
                      background: "#ef4444",
                      display: "inline-block",
                    }}
                  />
                  <span style={{ fontSize: "13px", fontWeight: "700", color: "#db2777" }}>
                    {formatTimer(recordingSeconds)}
                  </span>
                </div>
                <strong style={{ fontSize: "16px", color: "#c026d3", display: "block" }}>
                  Listening... Tap to Send
                </strong>
                <span style={{ fontSize: "12px", color: "#a855f7" }}>
                  Take your time: speak your items, name, phone number or address
                </span>
              </div>
            )}

            {voiceState === "processing" && (
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "4px" }}>
                <strong style={{ fontSize: "15px", color: "#64748b" }}>Thinking...</strong>
                <span style={{ fontSize: "12px", color: "#94a3b8" }}>Consulting business knowledge & catalog</span>
              </div>
            )}

            {voiceState === "speaking" && (
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "6px" }}>
                <div style={{ display: "flex", gap: "3px", alignItems: "center", height: "26px" }}>
                  <span className="wave-bar" />
                  <span className="wave-bar" />
                  <span className="wave-bar" />
                  <span className="wave-bar" />
                  <span className="wave-bar" />
                </div>
                <strong style={{ fontSize: "15px", color: "#0284c7" }}>Speaking response...</strong>
                <span style={{ fontSize: "11px", color: "#64748b" }}>Tap button above to pause or mute</span>
              </div>
            )}
          </div>
        </section>

        {/* Mandatory Rides Technologies Footer Branding */}
        <footer
          style={{
            textAlign: "center",
            padding: "8px 0 16px 0",
            fontSize: "12px",
            color: "#64748b",
          }}
        >
          <p style={{ margin: 0 }}>
            Powered by <strong>Rides AI</strong> · <span style={{ color: "#a855f7", fontWeight: "700" }}>Owned by Rides Technologies</span>
          </p>
        </footer>
      </div>

      {/* Customer Contact Details Modal */}
      {showContactModal && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(15, 23, 42, 0.45)",
            backdropFilter: "blur(4px)",
            display: "grid",
            placeItems: "center",
            padding: "16px",
            zIndex: 1000,
          }}
        >
          <div
            style={{
              width: "100%",
              maxWidth: "420px",
              background: "#ffffff",
              borderRadius: "20px",
              padding: "24px",
              boxShadow: "0 20px 40px rgba(0, 0, 0, 0.15)",
              border: "1px solid #f5d0fe",
            }}
          >
            <h3 style={{ margin: "0 0 6px 0", fontSize: "18px", color: "#0f172a" }}>
              Customer Details
            </h3>
            <p style={{ margin: "0 0 16px 0", fontSize: "13px", color: "#64748b" }}>
              These optional details help the voice agent associate your orders and contact you for deliveries.
            </p>

            <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
              <div>
                <label style={{ fontSize: "12px", fontWeight: "600", color: "#475569" }}>Full Name</label>
                <input
                  style={{
                    width: "100%",
                    boxSizing: "border-box",
                    padding: "10px 12px",
                    borderRadius: "10px",
                    border: "1px solid #cbd5e1",
                    marginTop: "4px",
                    fontSize: "14px",
                  }}
                  placeholder="e.g. Kamran Ali"
                  value={customer.name}
                  onChange={(e) => setCustomer({ ...customer, name: e.target.value })}
                />
              </div>

              <div>
                <label style={{ fontSize: "12px", fontWeight: "600", color: "#475569" }}>Phone Number</label>
                <input
                  style={{
                    width: "100%",
                    boxSizing: "border-box",
                    padding: "10px 12px",
                    borderRadius: "10px",
                    border: "1px solid #cbd5e1",
                    marginTop: "4px",
                    fontSize: "14px",
                  }}
                  placeholder="e.g. 03001234567"
                  value={customer.phone}
                  onChange={(e) => setCustomer({ ...customer, phone: e.target.value })}
                />
              </div>

              <div>
                <label style={{ fontSize: "12px", fontWeight: "600", color: "#475569" }}>Email (Optional)</label>
                <input
                  type="email"
                  style={{
                    width: "100%",
                    boxSizing: "border-box",
                    padding: "10px 12px",
                    borderRadius: "10px",
                    border: "1px solid #cbd5e1",
                    marginTop: "4px",
                    fontSize: "14px",
                  }}
                  placeholder="e.g. customer@example.com"
                  value={customer.email}
                  onChange={(e) => setCustomer({ ...customer, email: e.target.value })}
                />
              </div>
            </div>

            <div style={{ marginTop: "20px", display: "flex", justifyContent: "flex-end", gap: "8px" }}>
              <button
                type="button"
                onClick={() => setShowContactModal(false)}
                style={{
                  background: "linear-gradient(135deg, #ff77ff 0%, #ec4899 100%)",
                  border: "none",
                  borderRadius: "10px",
                  padding: "10px 20px",
                  color: "#ffffff",
                  fontSize: "13px",
                  fontWeight: "700",
                  cursor: "pointer",
                }}
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
