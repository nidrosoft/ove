"""Helper to configure Twilio SIP trunk for LiveKit integration.

Run: python scripts/setup_twilio_sip.py

This creates a Twilio SIP trunk pointed at your LiveKit SIP endpoint.
You'll need your LiveKit SIP endpoint URL (from LiveKit Cloud dashboard
or your self-hosted LiveKit server).

Prerequisites:
  - TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN in .env
  - A LiveKit SIP endpoint URL
"""
import os
import sys

from dotenv import load_dotenv
from twilio.rest import Client

load_dotenv()


def main():
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")

    if not account_sid or not auth_token:
        print("Error: Set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN in .env")
        sys.exit(1)

    # Prompt for LiveKit SIP endpoint
    livekit_sip_uri = input(
        "Enter your LiveKit SIP endpoint URI\n"
        "(e.g., sip:your-project.sip.livekit.cloud): "
    ).strip()

    if not livekit_sip_uri:
        print("Error: SIP URI is required.")
        sys.exit(1)

    client = Client(account_sid, auth_token)

    # Create SIP trunk
    trunk = client.trunking.v1.trunks.create(
        friendly_name="Omnira Voice Engine - LiveKit",
        secure=False,
    )
    print(f"SIP Trunk created: {trunk.sid}")

    # Add origination URI (where Twilio sends calls)
    origination = client.trunking.v1.trunks(trunk.sid).origination_urls.create(
        friendly_name="LiveKit SIP Gateway",
        sip_url=livekit_sip_uri,
        priority=1,
        weight=1,
        enabled=True,
    )
    print(f"Origination URI added: {origination.sid}")

    # Instructions for next steps
    phone_number = os.getenv("TWILIO_PHONE_NUMBER", "your Twilio number")
    print(f"\n{'='*60}")
    print("NEXT STEPS")
    print(f"{'='*60}")
    print(f"\n1. Go to https://console.twilio.com/")
    print(f"2. Navigate to Phone Numbers > Manage > Active Numbers")
    print(f"3. Click on {phone_number}")
    print(f"4. Under 'Voice Configuration':")
    print(f"   - Set 'Configure with' to 'SIP Trunk'")
    print(f"   - Select '{trunk.friendly_name}' ({trunk.sid})")
    print(f"5. Save")
    print(f"\nNow calls to {phone_number} will route to your LiveKit agent!")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
