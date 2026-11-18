"""
Isolated 4-Stage Diagnostic Script for WhatsApp Outbound Voice Notes.

Tests each pipeline stage sequentially:
  Stage 1 (TTS): Generate short test voice clip using audio_service.synthesize_speech.
  Stage 2 (Codec Check): Verify file size and probe codec via ffprobe.
  Stage 3 (Meta Media Upload): Upload file to Meta's /media endpoint and log response.
  Stage 4 (Meta Message Send): Send audio message with and without 'voice': True to test recipient.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

# Add project root to sys.path
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

import requests
from django.conf import settings
from operations.audio_service import synthesize_speech
from operations.whatsapp_storage import _load_all_configs

def mask_secret(val: str) -> str:
    if not val:
        return "<EMPTY>"
    s = str(val).strip()
    if len(s) <= 10:
        return "***"
    return f"{s[:6]}...{s[-4:]}"


def run_diagnostic(recipient_phone: str = "923090139836"):
    print("=================================================================")
    print("🔍 RIDES AI: Outbound WhatsApp Voice Note Diagnostic")
    print("=================================================================")

    # -------------------------------------------------------------------------
    # Credentials & Target Resolution
    # -------------------------------------------------------------------------
    configs = _load_all_configs()
    target_cfg = None
    target_key = None

    # Find the first active configuration or config with credentials
    for k, v in configs.items():
        if isinstance(v, dict) and v.get("phone_number_id") and v.get("access_token"):
            target_cfg = v
            target_key = k
            if v.get("is_active"):
                break

    if not target_cfg:
        print("❌ FATAL: No configured WhatsApp credentials found in whatsapp_config.json")
        return

    phone_number_id = str(target_cfg.get("phone_number_id", "")).strip()
    access_token = str(target_cfg.get("access_token", "")).strip()
    graph_api_version = "v21.0"

    # Allow recipient override via CLI argument
    if len(sys.argv) > 1:
        recipient_phone = sys.argv[1].strip()

    clean_to = recipient_phone.replace("+", "").replace(" ", "").replace("-", "")

    print(f"🏢 Config Tenant Key    : {target_key}")
    print(f"📱 Phone Number ID      : {phone_number_id}")
    print(f"🔑 Access Token         : {mask_secret(access_token)}")
    print(f"🎯 Test Recipient Phone : {clean_to}")
    print(f"🌐 Graph API Version    : {graph_api_version}")
    print("-----------------------------------------------------------------")

    # -------------------------------------------------------------------------
    # STAGE 1: TTS Generation (OpenAI API)
    # -------------------------------------------------------------------------
    print("\n▶ [STAGE 1] Text-to-Speech (TTS) Synthesis...")
    test_text = "Hello! This is a test voice note from Rides AI."
    print(f"   Input Text: \"{test_text}\"")

    try:
        audio_bytes = synthesize_speech(
            text=test_text,
            voice="alloy",
            model="tts-1",
            response_format="opus"
        )
    except Exception as e:
        print(f"❌ [STAGE 1 FAILED] Exception during synthesize_speech: {e}")
        return

    if not audio_bytes or len(audio_bytes) == 0:
        print("❌ [STAGE 1 FAILED] synthesize_speech returned None or 0 bytes.")
        return

    print(f"✅ [STAGE 1 SUCCESS] Generated {len(audio_bytes)} bytes of audio data.")

    # Save to temporary file for inspection
    temp_audio_path = CURRENT_DIR / "temp_diagnostic_voice.ogg"
    with open(temp_audio_path, "wb") as f:
        f.write(audio_bytes)
    print(f"   Saved temporary file: {temp_audio_path}")

    # -------------------------------------------------------------------------
    # STAGE 2: Codec Check via ffprobe
    # -------------------------------------------------------------------------
    print("\n▶ [STAGE 2] Codec & Audio Stream Verification...")
    print(f"   File Size: {os.path.getsize(temp_audio_path)} bytes")

    ffprobe_cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(temp_audio_path)
    ]

    try:
        proc = subprocess.run(ffprobe_cmd, capture_output=True, text=True, check=True)
        probe_data = json.loads(proc.stdout)
        streams = probe_data.get("streams", [])
        fmt = probe_data.get("format", {})

        if streams:
            audio_stream = streams[0]
            codec_name = audio_stream.get("codec_name")
            channels = audio_stream.get("channels")
            sample_rate = audio_stream.get("sample_rate")
            duration = audio_stream.get("duration") or fmt.get("duration")
            format_name = fmt.get("format_name")

            print(f"✅ [STAGE 2 SUCCESS] ffprobe Stream Details:")
            print(f"   • Container Format : {format_name}")
            print(f"   • Codec Name       : {codec_name}")
            print(f"   • Channels         : {channels} ({'Mono' if channels == 1 else 'Stereo'})")
            print(f"   • Sample Rate      : {sample_rate} Hz")
            print(f"   • Duration         : {duration} s")
        else:
            print("⚠️ [STAGE 2 WARNING] ffprobe returned no streams in the audio container.")
    except FileNotFoundError:
        print("⚠️ [STAGE 2 NOTICE] ffprobe is not installed or not in PATH.")
    except Exception as e:
        print(f"⚠️ [STAGE 2 WARNING] ffprobe inspection failed: {e}")

    # -------------------------------------------------------------------------
    # STAGE 3: Meta Media Upload (POST /{PHONE_NUMBER_ID}/media)
    # -------------------------------------------------------------------------
    print(f"\n▶ [STAGE 3] Meta Media Upload to POST /{phone_number_id}/media...")
    upload_url = f"https://graph.facebook.com/{graph_api_version}/{phone_number_id}/media"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "User-Agent": "RidesAI-Diagnostic/1.0",
    }
    data = {
        "messaging_product": "whatsapp",
        "type": "audio/ogg",
    }
    files = {
        "file": ("voice_note.ogg", audio_bytes, "audio/ogg"),
    }

    uploaded_media_id = None
    try:
        up_resp = requests.post(upload_url, headers=headers, data=data, files=files, timeout=30)
        print(f"   UPLOAD STATUS   : HTTP {up_resp.status_code}")
        print(f"   UPLOAD RESPONSE : {up_resp.text}")

        if up_resp.status_code in (200, 201):
            up_json = up_resp.json()
            uploaded_media_id = up_json.get("id")
            print(f"✅ [STAGE 3 SUCCESS] Extracted media_id: {uploaded_media_id}")
        else:
            print(f"❌ [STAGE 3 FAILED] Meta rejected media upload with HTTP {up_resp.status_code}.")
            return
    except Exception as e:
        print(f"❌ [STAGE 3 EXCEPTION] Network error during upload: {e}")
        return

    # -------------------------------------------------------------------------
    # STAGE 4: Meta Message Send (POST /{PHONE_NUMBER_ID}/messages)
    # -------------------------------------------------------------------------
    print(f"\n▶ [STAGE 4] Meta Message Send to POST /{phone_number_id}/messages...")
    messages_url = f"https://graph.facebook.com/{graph_api_version}/{phone_number_id}/messages"
    msg_headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "User-Agent": "RidesAI-Diagnostic/1.0",
    }

    # Test 4A: Payload with "voice": True (Requested by user diagnostic requirement)
    payload_voice_true = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": clean_to,
        "type": "audio",
        "audio": {
            "id": uploaded_media_id,
            "voice": True
        }
    }

    print("   [Test 4A] Dispatching with payload: 'voice': True...")
    try:
        resp_a = requests.post(messages_url, headers=msg_headers, json=payload_voice_true, timeout=25)
        print(f"   MESSAGE STATUS (4A)   : HTTP {resp_a.status_code}")
        print(f"   MESSAGE RESPONSE (4A) : {resp_a.text}")
        if resp_a.status_code in (200, 201):
            print("✅ [Test 4A SUCCESS] Message accepted by Meta Cloud API.")
        else:
            print("❌ [Test 4A FAILED] Message rejected by Meta Cloud API.")
    except Exception as e:
        print(f"❌ [Test 4A EXCEPTION] Error: {e}")

    # Test 4B: Standard payload without "voice": True (as currently in whatsapp_service.py)
    payload_standard = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": clean_to,
        "type": "audio",
        "audio": {
            "id": uploaded_media_id
        }
    }

    print("\n   [Test 4B] Dispatching with standard payload: without 'voice': True...")
    try:
        resp_b = requests.post(messages_url, headers=msg_headers, json=payload_standard, timeout=25)
        print(f"   MESSAGE STATUS (4B)   : HTTP {resp_b.status_code}")
        print(f"   MESSAGE RESPONSE (4B) : {resp_b.text}")
        if resp_b.status_code in (200, 201):
            print("✅ [Test 4B SUCCESS] Message accepted by Meta Cloud API.")
        else:
            print("❌ [Test 4B FAILED] Message rejected by Meta Cloud API.")
    except Exception as e:
        print(f"❌ [Test 4B EXCEPTION] Error: {e}")

    print("\n=================================================================")
    print("🏁 Diagnostic Run Completed.")
    print("=================================================================")


if __name__ == "__main__":
    run_diagnostic()
