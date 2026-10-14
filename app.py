"""
Voice Command Recognition Web Application
Cloud Computing Project - Amazon Lex V2 & Serverless Lambda
Backend: Python 3 + Flask + Boto3
"""

import os
import io
import time
import json
import base64
import logging
from flask import Flask, request, jsonify, render_template, send_from_directory
from dotenv import load_dotenv
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

# Load environment variables
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder="templates", static_folder="static")

# Configuration
MOCK_AWS = os.getenv("MOCK_AWS", "false").lower() in ("true", "1", "yes")
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
LEX_BOT_ID = os.getenv("LEX_BOT_ID", "")
LEX_BOT_ALIAS_ID = os.getenv("LEX_BOT_ALIAS_ID", "TSTALIASID")
LEX_LOCALE_ID = os.getenv("LEX_LOCALE_ID", "en_US")
SESSION_ID = "voice-session-student-001"

# In-memory virtual smart home state for visualization
device_states = {
    "living_room_light": {"name": "Living Room Light", "type": "light", "room": "living room", "state": "off", "brightness": 100, "color": "#fffaed"},
    "kitchen_light": {"name": "Kitchen Light", "type": "light", "room": "kitchen", "state": "off", "brightness": 100, "color": "#ffffff"},
    "fan": {"name": "Bedroom Ceiling Fan", "type": "fan", "room": "bedroom", "state": "off", "speed": 1},
    "ac": {"name": "Smart Air Conditioner", "type": "ac", "room": "living room", "state": "off", "temp": 24, "mode": "cool"},
    "door_lock": {"name": "Main Entrance Lock", "type": "lock", "room": "front door", "state": "locked"}
}

def get_lex_client():
    """Initializes and returns boto3 Lex V2 Runtime client."""
    return boto3.client(
        "lexv2-runtime",
        region_name=AWS_REGION,
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
    )


def update_virtual_devices(action, device_name, room_name, value=None):
    """Updates internal device states based on extracted slots."""
    updated = []
    action = (action or "").lower().strip()
    device_name = (device_name or "").lower().strip()
    room_name = (room_name or "").lower().strip()

    for dev_id, dev in device_states.items():
        match_room = (room_name in dev["room"]) or not room_name or (room_name in ("house", "room", "all"))
        match_device = (device_name in dev["type"]) or (device_name in dev_id) or (device_name in ("device", "devices", "all"))

        if match_room and match_device:
            if action in ("on", "turn on", "activate", "start", "enable"):
                dev["state"] = "on"
                updated.append(dev_id)
            elif action in ("off", "turn off", "deactivate", "stop", "disable"):
                dev["state"] = "off"
                updated.append(dev_id)
            elif action in ("lock",):
                if dev["type"] == "lock":
                    dev["state"] = "locked"
                    updated.append(dev_id)
            elif action in ("unlock", "open"):
                if dev["type"] == "lock":
                    dev["state"] = "unlocked"
                    updated.append(dev_id)

            # Value updates (e.g., temperature or brightness)
            if value:
                try:
                    num_val = int("".join(filter(str.isdigit, str(value))))
                    if dev["type"] == "ac":
                        dev["temp"] = max(16, min(30, num_val))
                        dev["state"] = "on"
                        updated.append(dev_id)
                    elif dev["type"] == "light":
                        dev["brightness"] = max(10, min(100, num_val))
                        updated.append(dev_id)
                except ValueError:
                    pass

    return updated


def mock_lex_processor(text_command):
    """
    Simulates AWS Lex V2 ASR and NLU locally for offline testing and demos
    when credentials are not yet entered.
    """
    text_lower = (text_command or "").lower().strip()
    if not text_lower:
        text_lower = "turn on the living room light"

    start_time = time.time()
    time.sleep(0.08)  # Simulate small network round-trip

    intent = "DeviceControlIntent"
    slots = {}
    
    # Action detection
    if "turn off" in text_lower or "switch off" in text_lower or "power off" in text_lower or "stop" in text_lower:
        action = "off"
    elif "turn on" in text_lower or "switch on" in text_lower or "power on" in text_lower or "start" in text_lower:
        action = "on"
    elif "lock" in text_lower and "unlock" not in text_lower:
        action = "lock"
    elif "unlock" in text_lower or "open" in text_lower:
        action = "unlock"
    elif "off" in text_lower:
        action = "off"
    elif "on" in text_lower:
        action = "on"
    else:
        action = "set" if ("set" in text_lower or "change" in text_lower) else "toggle"

    # Device detection
    if "fan" in text_lower:
        device = "fan"
    elif "light" in text_lower or "lamp" in text_lower or "bulb" in text_lower:
        device = "light"
    elif "ac" in text_lower or "air conditioner" in text_lower or "cooling" in text_lower or "temperature" in text_lower:
        device = "ac"
    elif "door" in text_lower or "lock" in text_lower:
        device = "lock"
    else:
        device = "device"

    # Room detection
    if "kitchen" in text_lower:
        room = "kitchen"
    elif "bedroom" in text_lower:
        room = "bedroom"
    elif "living" in text_lower or "hall" in text_lower:
        room = "living room"
    elif "door" in text_lower or "front" in text_lower:
        room = "front door"
    else:
        # Default rooms by device
        room = "bedroom" if device == "fan" else ("living room" if device in ("light", "ac") else "front door")

    # Numeric value extraction (e.g., temperature 20 or brightness 80)
    import re
    numbers = re.findall(r"\b\d+\b", text_lower)
    value = numbers[0] if numbers else None

    # Handle status query intent
    if "status" in text_lower or "check" in text_lower or "how is" in text_lower or "is everything" in text_lower:
        intent = "QueryStatusIntent"
        message = f"Checking status: All {device} systems in {room} are functioning normally."
    else:
        slots = {
            "Action": {"value": {"interpretedValue": action}},
            "Device": {"value": {"interpretedValue": device}},
            "Room": {"value": {"interpretedValue": room}},
            "Value": {"value": {"interpretedValue": value}} if value else None
        }
        update_virtual_devices(action, device, room, value)
        if value:
            message = f"Got it. Setting the {room} {device} to {value}."
        elif action in ("lock", "unlock"):
            message = f"Got it. Successfully {action}ed the {room} {device}."
        else:
            message = f"Got it. Turning {action} the {device} in the {room}."

    latency_ms = int((time.time() - start_time) * 1000)

    return {
        "status": "success",
        "mode": "Simulated (Local Mock Mode - MOCK_AWS=true)",
        "transcript": text_command,
        "intent": intent,
        "confidence": 0.99,
        "slots": {k: (v["value"]["interpretedValue"] if v else None) for k, v in slots.items()},
        "message": message,
        "latency_ms": latency_ms,
        "audio_base64": None,
        "device_states": device_states
    }


@app.route("/")
def index():
    return render_template("index.html", mock_mode=MOCK_AWS)


@app.route("/api/devices", methods=["GET"])
def get_devices():
    return jsonify({"status": "success", "devices": device_states})


@app.route("/api/command/text", methods=["POST"])
def process_text_command():
    data = request.get_json() or {}
    text = data.get("text", "").strip()

    if not text:
        return jsonify({"status": "error", "message": "No command text provided"}), 400

    if MOCK_AWS or not LEX_BOT_ID or LEX_BOT_ID == "YOUR_LEX_BOT_ID":
        logger.info(f"Mock Mode: Processing text command: '{text}'")
        return jsonify(mock_lex_processor(text))

    # Real AWS Lex V2 invocation
    start_time = time.time()
    try:
        client = get_lex_client()
        response = client.recognize_text(
            botId=LEX_BOT_ID,
            botAliasId=LEX_BOT_ALIAS_ID,
            localeId=LEX_LOCALE_ID,
            sessionId=SESSION_ID,
            text=text
        )

        latency_ms = int((time.time() - start_time) * 1000)
        session_state = response.get("sessionState", {})
        intent = session_state.get("intent", {})
        intent_name = intent.get("name", "Unknown")
        slots = intent.get("slots", {}) or {}

        # Extract slot values
        parsed_slots = {}
        for k, v in slots.items():
            if v and "value" in v:
                parsed_slots[k] = v["value"].get("interpretedValue") or v["value"].get("originalValue")

        # Extract message from messages array
        messages = response.get("messages", [])
        bot_message = messages[0].get("content") if messages else "Command executed."

        # Update local device representations
        action = parsed_slots.get("Action")
        device = parsed_slots.get("Device")
        room = parsed_slots.get("Room")
        val = parsed_slots.get("Value")
        update_virtual_devices(action, device, room, val)

        return jsonify({
            "status": "success",
            "mode": "Live AWS Lex V2 (Text)",
            "transcript": text,
            "intent": intent_name,
            "confidence": 1.0,
            "slots": parsed_slots,
            "message": bot_message,
            "latency_ms": latency_ms,
            "device_states": device_states,
            "raw_lex_response": response
        })

    except Exception as e:
        logger.error(f"Error calling AWS Lex: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e), "hint": "Check AWS credentials or switch to MOCK_AWS=true in .env"}), 500


@app.route("/api/command/voice", methods=["POST"])
def process_voice_command():
    transcript = request.form.get("transcript", "").strip()
    
    # Check if voice transcription was passed from browser speech engine
    if MOCK_AWS or not LEX_BOT_ID or LEX_BOT_ID == "YOUR_LEX_BOT_ID":
        spoken_text = transcript if transcript else "turn on the living room light"
        logger.info(f"Mock Mode: Processing voice command transcript: '{spoken_text}'")
        return jsonify(mock_lex_processor(spoken_text))

    if "audio" not in request.files:
        # If no raw audio file was sent but transcript was, fallback to text recognition with Lex
        if transcript:
            return process_text_direct(transcript)
        return jsonify({"status": "error", "message": "No audio file or transcript received"}), 400

    audio_file = request.files["audio"]
    audio_bytes = audio_file.read()

    if len(audio_bytes) == 0:
        if transcript:
            return process_text_direct(transcript)
        return jsonify({"status": "error", "message": "Uploaded audio is empty"}), 400

    start_time = time.time()
    try:
        client = get_lex_client()

        # For raw 16kHz PCM audio, strip RIFF WAV header (44 bytes) if present
        if audio_bytes.startswith(b'RIFF') and len(audio_bytes) > 44:
            payload_bytes = audio_bytes[44:]
        else:
            payload_bytes = audio_bytes
        
        response = client.recognize_utterance(
            botId=LEX_BOT_ID,
            botAliasId=LEX_BOT_ALIAS_ID,
            localeId=LEX_LOCALE_ID,
            sessionId=SESSION_ID,
            requestContentType="audio/l16; rate=16000; channels=1",
            responseContentType="audio/mpeg",
            inputStream=payload_bytes
        )

        latency_ms = int((time.time() - start_time) * 1000)

        # Lex V2 returns metadata in base64 HTTP response headers
        lex_transcript = response.get("inputTranscript", transcript or "Voice command")
        
        session_state_raw = response.get("sessionState")
        session_state = json.loads(base64.b64decode(session_state_raw).decode("utf-8")) if session_state_raw else {}
        intent = session_state.get("intent", {})
        intent_name = intent.get("name", "Unknown")
        slots = intent.get("slots", {}) or {}

        parsed_slots = {}
        for k, v in slots.items():
            if v and "value" in v:
                parsed_slots[k] = v["value"].get("interpretedValue") or v["value"].get("originalValue")

        # Parse messages header
        messages_raw = response.get("messages")
        messages = json.loads(base64.b64decode(messages_raw).decode("utf-8")) if messages_raw else []
        bot_message = messages[0].get("content") if messages else "Command executed."

        # Read Polly synthesized response audio stream
        audio_stream = response.get("audioStream")
        audio_b64 = None
        if audio_stream:
            audio_out = audio_stream.read()
            audio_b64 = base64.b64encode(audio_out).decode("utf-8")

        # Update local virtual devices
        action = parsed_slots.get("Action")
        device = parsed_slots.get("Device")
        room = parsed_slots.get("Room")
        val = parsed_slots.get("Value")
        update_virtual_devices(action, device, room, val)

        return jsonify({
            "status": "success",
            "mode": "Live AWS Lex V2 (Audio Stream Recognized)",
            "transcript": lex_transcript,
            "intent": intent_name,
            "slots": parsed_slots,
            "message": bot_message,
            "latency_ms": latency_ms,
            "audio_base64": audio_b64,
            "device_states": device_states
        })

    except Exception as e:
        logger.error(f"Error calling AWS Lex RecognizeUtterance: {e}", exc_info=True)
        # If Lex utterance fails (e.g. format mismatch), fallback to recognized transcript if available
        if transcript:
            logger.info("Falling back to text recognition via recognized transcript...")
            return process_text_direct(transcript)
        return jsonify({"status": "error", "message": str(e)}), 500


def process_text_direct(text):
    """Helper to process text directly through Lex."""
    start_time = time.time()
    try:
        client = get_lex_client()
        response = client.recognize_text(
            botId=LEX_BOT_ID,
            botAliasId=LEX_BOT_ALIAS_ID,
            localeId=LEX_LOCALE_ID,
            sessionId=SESSION_ID,
            text=text
        )
        latency_ms = int((time.time() - start_time) * 1000)
        session_state = response.get("sessionState", {})
        intent = session_state.get("intent", {})
        intent_name = intent.get("name", "Unknown")
        slots = intent.get("slots", {}) or {}

        parsed_slots = {}
        for k, v in slots.items():
            if v and "value" in v:
                parsed_slots[k] = v["value"].get("interpretedValue") or v["value"].get("originalValue")

        messages = response.get("messages", [])
        bot_message = messages[0].get("content") if messages else "Command executed."

        action = parsed_slots.get("Action")
        device = parsed_slots.get("Device")
        room = parsed_slots.get("Room")
        val = parsed_slots.get("Value")
        update_virtual_devices(action, device, room, val)

        return jsonify({
            "status": "success",
            "mode": "Live AWS Lex V2 (Text Fallback)",
            "transcript": text,
            "intent": intent_name,
            "slots": parsed_slots,
            "message": bot_message,
            "latency_ms": latency_ms,
            "device_states": device_states,
            "raw_lex_response": response
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print("\n" + "="*60)
    print(" [PROJECT] Voice Command Recognition - Cloud Computing")
    print(f" [URL] Dashboard running at: http://127.0.0.1:{port}")
    print(f" [MODE] AWS Lex Integration: {'SIMULATED (MOCK)' if MOCK_AWS or not LEX_BOT_ID else 'LIVE AWS CLOUD'}")
    print("="*60 + "\n")
    app.run(host="0.0.0.0", port=port, debug=False)
