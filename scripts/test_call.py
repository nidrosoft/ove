"""Quick test — create a LiveKit room and connect via browser to test the agent.

Run: python scripts/test_call.py

This will print a URL you can open in your browser to talk to the agent.
"""
import asyncio
import os

from dotenv import load_dotenv
from livekit import api

load_dotenv()


async def main():
    lk_api = api.LiveKitAPI(
        os.getenv("LIVEKIT_URL", "http://localhost:7880"),
        os.getenv("LIVEKIT_API_KEY", "devkey"),
        os.getenv("LIVEKIT_API_SECRET", "secret"),
    )

    # Create a room
    room = await lk_api.room.create_room(
        api.CreateRoomRequest(name="test-call-001")
    )
    print(f"Room created: {room.name}")

    # Generate a token for the test caller
    token = (
        api.AccessToken(
            os.getenv("LIVEKIT_API_KEY", "devkey"),
            os.getenv("LIVEKIT_API_SECRET", "secret"),
        )
        .with_identity("test-caller")
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=room.name,
            )
        )
        .to_jwt()
    )

    print(f"\n{'='*60}")
    print(f"TEST YOUR AGENT")
    print(f"{'='*60}")
    print(f"\nOpen the LiveKit Agents Playground:")
    print(f"https://agents-playground.livekit.io/")
    print(f"\nOr connect manually with this token:")
    print(f"Room: {room.name}")
    print(f"Token: {token[:50]}...")
    print(f"\nLiveKit URL: {os.getenv('LIVEKIT_URL', 'ws://localhost:7880')}")
    print(f"{'='*60}\n")

    await lk_api.aclose()


if __name__ == "__main__":
    asyncio.run(main())
