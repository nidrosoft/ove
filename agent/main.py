"""Entry point — LiveKit Agent worker."""
import asyncio
import logging

from dotenv import load_dotenv
from livekit.agents import WorkerOptions, cli

from agent.voice_agent import OmniraReceptionist, create_agent_session

# Load environment
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("omnira")


async def entrypoint(ctx):
    """Handle a new call/room connection."""
    logger.info(f"New connection: room={ctx.room.name}")

    await ctx.connect()

    participant = await ctx.wait_for_participant()
    logger.info(f"Participant joined: {participant.identity}")

    session = create_agent_session()

    agent = OmniraReceptionist()
    await session.start(
        agent=agent,
        room=ctx.room,
    )

    logger.info(f"Agent started in room {ctx.room.name}")


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
        ),
    )
