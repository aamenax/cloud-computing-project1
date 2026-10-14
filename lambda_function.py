"""
AWS Lambda Fulfillment Handler for Amazon Lex V2
Project: Voice Command Recognition - Cloud Computing Lab
Cost: $0 (Runs 100% within AWS Free Tier: 1M invocations/month free)
"""

import json
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """
    Main Lambda entry point triggered by AWS Lex V2 DialogCodeHook or FulfillmentCodeHook.
    Processes user intent and extracted slots, executes command, and returns Lex V2 format response.
    """
    logger.info(f"Incoming Lex Event: {json.dumps(event)}")
    
    # Extract intent and session information from Lex V2 event
    session_state = event.get('sessionState', {})
    intent = session_state.get('intent', {})
    intent_name = intent.get('name', '')
    slots = intent.get('slots', {}) or {}
    invocation_source = event.get('invocationSource', 'FulfillmentCodeHook')

    # Default fallback message
    fulfillment_text = "I received your command, but I did not recognize the required action."
    device_state_update = None

    # Handle Intent: DeviceControlIntent
    if intent_name == 'DeviceControlIntent':
        action = get_slot_value(slots, 'Action', default='toggle').lower()
        device = get_slot_value(slots, 'Device', default='device').lower()
        room = get_slot_value(slots, 'Room', default='living room').lower()
        value = get_slot_value(slots, 'Value', default=None)

        logger.info(f"Processing DeviceControlIntent: action={action}, device={device}, room={room}, value={value}")

        if value:
            fulfillment_text = f"Setting the {room} {device} to {value}."
        else:
            fulfillment_text = f"Turning {action} the {device} in the {room}."

        device_state_update = {
            "device": device,
            "action": action,
            "room": room,
            "value": value,
            "status": "SUCCESS"
        }

    # Handle Intent: QueryStatusIntent
    elif intent_name == 'QueryStatusIntent':
        device = get_slot_value(slots, 'Device', default='all devices').lower()
        room = get_slot_value(slots, 'Room', default='the house').lower()
        fulfillment_text = f"Checking the current status of the {device} in {room}. All systems are operating normally."
        device_state_update = {
            "device": device,
            "action": "query",
            "room": room,
            "status": "QUERY_OK"
        }

    # Handle Intent: FallbackIntent or unhandled intents
    else:
        fulfillment_text = "Sorry, I am not sure how to execute that command. You can say 'turn on living room light' or 'set AC to 22 degrees'."

    # Construct the Amazon Lex V2 response schema
    response = {
        "sessionState": {
            "dialogAction": {
                "type": "Close"
            },
            "intent": {
                "name": intent_name,
                "state": "Fulfilled",
                "slots": slots
            },
            "sessionAttributes": {
                "lastDeviceUpdate": json.dumps(device_state_update) if device_state_update else "{}"
            }
        },
        "messages": [
            {
                "contentType": "PlainText",
                "content": fulfillment_text
            }
        ]
    }

    logger.info(f"Returning Lex Response: {json.dumps(response)}")
    return response


def get_slot_value(slots, slot_name, default=None):
    """Safely extracts the resolved value from a Lex V2 slot dictionary."""
    if not slots or slot_name not in slots or not slots[slot_name]:
        return default
    
    slot_obj = slots[slot_name]
    value_obj = slot_obj.get('value', {})
    
    # Lex V2 provides interpretedValue (resolved) or originalValue (raw spoken)
    return value_obj.get('interpretedValue') or value_obj.get('originalValue') or default
