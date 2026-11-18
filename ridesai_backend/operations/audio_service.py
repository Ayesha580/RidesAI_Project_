"""
Audio Service for Rides AI Platform.

Handles Speech-to-Text (STT) transcription of customer voice notes
received via WhatsApp, utilizing Groq's high-speed whisper-large-v3 model
with automatic fallback to OpenAI Whisper.
"""

import io
import logging
import os
from typing import Optional

from django.conf import settings

logger = logging.getLogger("operations.whatsapp")


def transcribe_audio(audio_bytes: bytes, filename: str = "audio.ogg") -> Optional[str]:
    """
    Transcribes audio bytes into text using Groq's whisper-large-v3 (or OpenAI fallback).

    :param audio_bytes: Binary audio payload (typically .ogg Opus from WhatsApp Meta Cloud API).
    :param filename: Filename hint for the multipart payload, defaults to 'audio.ogg'.
    :return: Transcribed text string, or None if transcription fails.
    """
    if not audio_bytes or len(audio_bytes) < 100:
        logger.warning(f"[Audio STT] Audio payload is too small ({len(audio_bytes) if audio_bytes else 0} bytes).")
        return None

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
            )

            text = getattr(transcription, "text", "") or ""
            text = text.strip()
            if text:
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
            )

            text = getattr(transcription, "text", "") or ""
            text = text.strip()
            if text:
                logger.info(f"[Audio STT] OpenAI transcription succeeded: '{text}'")
                print(f"[STT Output] Voice Transcribed via OpenAI Whisper: '{text}'")
                return text

        except Exception as e:
            logger.error(f"[Audio STT] OpenAI Whisper transcription failed: {e}", exc_info=True)
            print(f"[Audio STT ERROR] OpenAI Whisper transcription failed: {e}")

    logger.error("[Audio STT] No transcription provider succeeded or API keys are missing.")
    return None


def synthesize_speech(
    text: str,
    voice: str = "shimmer",
    model: str = "tts-1",
    response_format: str = "opus"
) -> Optional[bytes]:
    """
    Synthesizes text into high-quality spoken audio using OpenAI TTS API.
    Uses 'opus' format (.ogg container) specifically required for WhatsApp voice notes.

    :param text: Text string to convert to speech.
    :param voice: Voice persona (e.g. 'alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer'). Defaults to 'alloy'.
    :param model: TTS model (defaults to 'tts-1').
    :param response_format: Audio format (defaults to 'opus' for WhatsApp voice note compatibility).
    :return: Binary audio bytes (.ogg Opus), or None if synthesis fails.
    """
    if not text or not str(text).strip():
        logger.warning("[Audio TTS] Text is empty; skipping speech synthesis.")
        return None

    clean_text = str(text).strip()
    openai_api_key = getattr(settings, "OPENAI_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "")
    if not openai_api_key or len(openai_api_key.strip()) < 10:
        logger.error("[Audio TTS] Missing or invalid OPENAI_API_KEY for speech synthesis.")
        return None

    try:
        from openai import OpenAI

        client = OpenAI(api_key=openai_api_key.strip(), timeout=30.0)
        logger.info(
            f"[Audio TTS] Synthesizing speech ({len(clean_text)} chars) with "
            f"voice='{voice}', model='{model}', format='{response_format}'..."
        )

        response = client.audio.speech.create(
            model=model,
            voice=voice,
            input=clean_text,
            response_format=response_format,
        )

        audio_bytes = response.content if hasattr(response, "content") else response.read()
        logger.info(f"[Audio TTS] Speech synthesis succeeded: generated {len(audio_bytes)} bytes.")
        print(f"[TTS Output] Generated {len(audio_bytes)} bytes of voice note audio ({response_format}).")
        return audio_bytes

    except Exception as e:
        logger.error(f"[Audio TTS ERROR] Speech synthesis failed: {e}", exc_info=True)
        print(f"[Audio TTS ERROR] Failed to synthesize speech: {e}")
        return None

