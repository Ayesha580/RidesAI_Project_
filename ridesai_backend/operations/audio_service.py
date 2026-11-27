"""
Audio Service for Rides AI Platform.

Handles Speech-to-Text (STT) transcription of customer voice notes
received via WhatsApp, utilizing Groq's high-speed whisper-large-v3 model
with automatic fallback to OpenAI Whisper.
"""

import io
import logging
import os
import re
from typing import Optional

from django.conf import settings

logger = logging.getLogger("operations.whatsapp")

NON_LATIN_SCRIPT_PATTERN = re.compile(r"[\u0900-\u097F\u0600-\u06FF]")

DEFAULT_STT_PROMPT = (
    "Customer speaking in English, Urdu, or Roman Urdu about restaurant menu, food orders, "
    "medicines, pharmacy, clinic appointments, or retail products. Phrases: menu bhej do, "
    "order karna hai, kya items hain, rate kya hai, zinger burger, fries, panadol. "
    "Pakistani phone numbers and digits: 03001234567, 03090139836, 03123456789, address, street."
)


def transliterate_to_roman_urdu(text: str) -> str:
    """
    Transliterates text containing Devanagari (Hindi) or Arabic/Urdu script into natural Roman Urdu
    using Groq (llama-3.1-8b-instant) or OpenAI (gpt-4o-mini).
    Ensures spoken Urdu voice notes transcribed into Hindi/Urdu script are stored & processed as clean Roman Urdu.
    """
    if not text or not NON_LATIN_SCRIPT_PATTERN.search(text):
        return text

    instruction = (
        "Transliterate the following spoken Urdu/Hindi customer message into natural Roman Urdu using "
        "ONLY English/Latin letters (keep English words like menu, burger, fries, order, delivery as-is). "
        "Do NOT translate meaning away or add commentary. Return ONLY the Roman Urdu sentence."
    )

    # 1. Try Groq (high-speed LLM)
    groq_api_key = getattr(settings, "GROQ_API_KEY", "") or os.environ.get("GROQ_API_KEY", "")
    if groq_api_key and len(groq_api_key.strip()) > 5:
        try:
            from groq import Groq
            client = Groq(api_key=groq_api_key.strip(), timeout=10.0)
            chat_completion = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": instruction},
                    {"role": "user", "content": text},
                ],
                model=getattr(settings, "GROQ_CHAT_MODEL", "llama-3.1-8b-instant"),
                temperature=0.0,
                max_tokens=150,
            )
            res = (chat_completion.choices[0].message.content or "").strip()
            if res.startswith('"') and res.endswith('"'):
                res = res[1:-1].strip()
            if res:
                logger.info(f"[Audio STT] Transliterated non-Latin script '{text}' -> '{res}' via Groq")
                return res
        except Exception as e:
            logger.warning(f"[Audio STT] Groq transliteration failed: {e}")

    # 2. Fallback to OpenAI (gpt-4o-mini)
    openai_api_key = getattr(settings, "OPENAI_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "")
    if openai_api_key and len(openai_api_key.strip()) > 10:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=openai_api_key.strip(), timeout=10.0)
            chat_completion = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": instruction},
                    {"role": "user", "content": text},
                ],
                model=getattr(settings, "OPENAI_MODEL", "gpt-4o-mini"),
                temperature=0.0,
                max_tokens=150,
            )
            res = (chat_completion.choices[0].message.content or "").strip()
            if res.startswith('"') and res.endswith('"'):
                res = res[1:-1].strip()
            if res:
                logger.info(f"[Audio STT] Transliterated non-Latin script '{text}' -> '{res}' via OpenAI")
                return res
        except Exception as e:
            logger.warning(f"[Audio STT] OpenAI transliteration failed: {e}")

    return text


def transcribe_audio(
    audio_bytes: bytes,
    filename: str = "audio.ogg",
    prompt: Optional[str] = None,
) -> Optional[str]:
    """
    Transcribes audio bytes into text using Groq's whisper-large-v3 (or OpenAI fallback).

    :param audio_bytes: Binary audio payload (typically .ogg Opus from WhatsApp Meta Cloud API).
    :param filename: Filename hint for the multipart payload, defaults to 'audio.ogg'.
    :param prompt: Optional conditioning prompt to guide Whisper STT on domain/multilingual vocabulary.
    :return: Transcribed text string (transliterated to Roman Urdu if Devanagari/Urdu script), or None.
    """
    if not audio_bytes or len(audio_bytes) < 100:
        logger.warning(f"[Audio STT] Audio payload is too small ({len(audio_bytes) if audio_bytes else 0} bytes).")
        return None

    stt_prompt = (prompt or DEFAULT_STT_PROMPT).strip()

    # Step 1: Try Groq whisper-large-v3 (Ultra-fast STT)
    groq_api_key = getattr(settings, "GROQ_API_KEY", "") or os.environ.get("GROQ_API_KEY", "")
    stt_model = getattr(settings, "GROQ_STT_MODEL", "whisper-large-v3")

    if groq_api_key and len(groq_api_key.strip()) > 5:
        try:
            from groq import Groq

            client = Groq(api_key=groq_api_key.strip(), timeout=30.0)
            logger.info(f"[Audio STT] Sending {len(audio_bytes)} bytes to Groq ({stt_model})...")

            transcription = client.audio.transcriptions.create(
                file=(filename, audio_bytes),
                model=stt_model,
                temperature=0.0,
                prompt=stt_prompt,
            )

            text = getattr(transcription, "text", "") or ""
            text = text.strip()
            if text:
                text = transliterate_to_roman_urdu(text)
                logger.info(f"[Audio STT] Groq transcription succeeded: '{text}'")
                print(f"[STT Output] Voice Transcribed via Groq: '{text}'")
                return text

        except Exception as e:
            logger.error(f"[Audio STT] Groq transcription failed: {e}", exc_info=True)
            print(f"[Audio STT Warning] Groq transcription failed: {e}. Trying fallback...")

    # Step 2: Fallback to OpenAI Whisper (whisper-1)
    openai_api_key = getattr(settings, "OPENAI_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "")
    if openai_api_key and len(openai_api_key.strip()) > 10:
        try:
            from openai import OpenAI

            client = OpenAI(api_key=openai_api_key.strip(), timeout=30.0)
            logger.info(f"[Audio STT] Sending {len(audio_bytes)} bytes to OpenAI Whisper (whisper-1)...")

            transcription = client.audio.transcriptions.create(
                file=(filename, audio_bytes),
                model="whisper-1",
                prompt=stt_prompt,
            )

            text = getattr(transcription, "text", "") or ""
            text = text.strip()
            if text:
                text = transliterate_to_roman_urdu(text)
                logger.info(f"[Audio STT] OpenAI transcription succeeded: '{text}'")
                print(f"[STT Output] Voice Transcribed via OpenAI Whisper: '{text}'")
                return text

        except Exception as e:
            logger.error(f"[Audio STT] OpenAI Whisper transcription failed: {e}", exc_info=True)
            print(f"[Audio STT ERROR] OpenAI Whisper transcription failed: {e}")

    logger.error("[Audio STT] No transcription provider succeeded or API keys are missing.")
    return None


def clean_text_for_tts(text: str) -> str:
    """
    Sanitizes text for OpenAI Text-to-Speech:
    1. Replaces currency signs ($850, Rs. 850, PKR 850) with natural spoken words ('850 rupees').
    2. Strips markdown symbols (*, _, #, ~, `, bullets •, -, etc.).
    3. Normalizes whitespace and removes symbol clutter so the voice sounds crisp and natural.
    """
    if not text:
        return ""
    import re
    cleaned = str(text)

    # 1. Currency conversion to spoken words
    cleaned = re.sub(r'\$\s*(\d+(?:\.\d+)?)', r'\1 rupees', cleaned)
    cleaned = re.sub(r'Rs\.?\s*(\d+(?:\.\d+)?)', r'\1 rupees', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'PKR\s*(\d+(?:\.\d+)?)', r'\1 rupees', cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace("$", " rupees ")

    # 2. Strip markdown headers (#, ##, etc.)
    cleaned = re.sub(r'#+\s*', '', cleaned)
    # Strip bold / italics / strikethrough / code formatting (*bold*, _italic_, ~strike~, `code`)
    cleaned = re.sub(r'[*_~`]', '', cleaned)
    # Strip bullet characters (•, \u2022) and line-start list markers
    cleaned = re.sub(r'[\u2022•]', ' ', cleaned)
    cleaned = re.sub(r'(?m)^\s*[\-\*]\s*', '', cleaned)
    # Strip markdown links [label](url) -> label
    cleaned = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', cleaned)
    # Collapse excessive exclamation marks
    cleaned = re.sub(r'!{2,}', '!', cleaned)

    # 3. Collapse extra whitespace
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


def synthesize_speech(
    text: str,
    voice: Optional[str] = None,
    model: Optional[str] = None,
    response_format: str = "mp3",
    speed: float = 0.92,
) -> Optional[bytes]:
    """
    Synthesizes text into high-quality spoken audio using OpenAI TTS API.
    Uses 'mp3' format so Evolution API's sendWhatsAppAudio converts clean MP3 directly
    to WhatsApp PTT without double-opus distortion.

    :param text: Text string to convert to speech.
    :param voice: Voice persona (e.g. 'nova', 'alloy', 'shimmer'). Defaults to 'nova' or settings.OPENAI_TTS_VOICE.
    :param model: TTS model (defaults to 'tts-1-hd' or settings.OPENAI_TTS_MODEL).
    :param response_format: Audio format (defaults to 'mp3').
    :param speed: Playback speed (defaults to 0.92 for crisp, unhurried pronunciation).
    :return: Binary audio bytes (.mp3), or None if synthesis fails.
    """
    if not text or not str(text).strip():
        logger.warning("[Audio TTS] Text is empty; skipping speech synthesis.")
        return None

    clean_text = clean_text_for_tts(text)
    if not clean_text:
        return None

    logger.info("[TTS Input Text] %s", clean_text)

    chosen_voice = voice or getattr(settings, "OPENAI_TTS_VOICE", "nova")
    chosen_model = model or getattr(settings, "OPENAI_TTS_MODEL", "tts-1-hd")
    chosen_speed = speed if speed is not None else float(getattr(settings, "OPENAI_TTS_SPEED", 0.92))

    openai_api_key = getattr(settings, "OPENAI_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "")
    if not openai_api_key or len(openai_api_key.strip()) < 10:
        logger.error("[Audio TTS] Missing or invalid OPENAI_API_KEY for speech synthesis.")
        return None

    try:
        from openai import OpenAI

        client = OpenAI(api_key=openai_api_key.strip(), timeout=30.0)
        logger.info(
            f"[Audio TTS] Synthesizing speech ({len(clean_text)} chars) with "
            f"voice='{chosen_voice}', model='{chosen_model}', format='{response_format}', speed={chosen_speed}..."
        )

        response = client.audio.speech.create(
            model=chosen_model,
            voice=chosen_voice,
            input=clean_text,
            response_format=response_format,
            speed=chosen_speed,
        )

        audio_bytes = response.content if hasattr(response, "content") else response.read()
        logger.info(f"[Audio TTS] Speech synthesis succeeded: generated {len(audio_bytes)} bytes.")
        print(f"[TTS Output] Generated {len(audio_bytes)} bytes of voice note audio ({response_format}).")
        return audio_bytes

    except Exception as e:
        logger.error(f"[Audio TTS ERROR] Speech synthesis failed: {e}", exc_info=True)
        print(f"[Audio TTS ERROR] Failed to synthesize speech: {e}")
        return None

