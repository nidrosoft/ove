"""Call recording via LiveKit Egress API → Supabase Storage."""
import logging
import os

from livekit import api

logger = logging.getLogger("omnira-recording")

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
SUPABASE_S3_ACCESS_KEY = os.getenv("SUPABASE_S3_ACCESS_KEY", "")
SUPABASE_S3_SECRET_KEY = os.getenv("SUPABASE_S3_SECRET_KEY", "")
SUPABASE_S3_REGION = os.getenv("SUPABASE_S3_REGION", "us-east-1")
RECORDING_BUCKET = "call-recordings"


def _get_supabase_s3_endpoint() -> str:
    """Build the Supabase Storage S3 endpoint from the Supabase URL."""
    if not SUPABASE_URL:
        return ""
    ref = SUPABASE_URL.replace("https://", "").split(".")[0]
    return f"https://{ref}.supabase.co/storage/v1/s3"


async def start_room_recording(room_name: str, call_id: str) -> str | None:
    """Start an audio-only room composite egress, uploading to Supabase Storage S3.

    Returns the egress_id if successful, None otherwise.
    """
    if not SUPABASE_S3_ACCESS_KEY or not SUPABASE_S3_SECRET_KEY:
        logger.warning("Supabase S3 credentials not configured — skipping recording")
        return None

    endpoint = _get_supabase_s3_endpoint()
    if not endpoint:
        logger.warning("SUPABASE_URL not configured — skipping recording")
        return None

    try:
        lk_api = api.LiveKitAPI()

        filepath = f"{call_id}.ogg"

        egress_request = api.RoomCompositeEgressRequest(
            room_name=room_name,
            audio_only=True,
            file_outputs=[
                api.EncodedFileOutput(
                    file_type=api.EncodedFileType.OGG,
                    filepath=filepath,
                    s3=api.S3Upload(
                        access_key=SUPABASE_S3_ACCESS_KEY,
                        secret=SUPABASE_S3_SECRET_KEY,
                        region=SUPABASE_S3_REGION,
                        endpoint=endpoint,
                        bucket=RECORDING_BUCKET,
                        force_path_style=True,
                    ),
                )
            ],
        )

        egress_info = await lk_api.egress.start_room_composite_egress(egress_request)
        egress_id = egress_info.egress_id
        logger.info(f"Recording started: egress_id={egress_id} room={room_name}")
        await lk_api.aclose()
        return egress_id

    except Exception as e:
        logger.error(f"Failed to start recording for room {room_name}: {e}")
        return None


def get_recording_url(call_id: str) -> str:
    """Build the public URL for a recording in Supabase Storage."""
    if not SUPABASE_URL:
        return ""
    ref = SUPABASE_URL.replace("https://", "").split(".")[0]
    return f"https://{ref}.supabase.co/storage/v1/object/public/{RECORDING_BUCKET}/{call_id}.ogg"


async def wait_for_egress(egress_id: str, timeout: float = 30.0) -> bool:
    """Poll the egress status until it completes or times out."""
    import asyncio

    if not egress_id:
        return False

    try:
        lk_api = api.LiveKitAPI()
        elapsed = 0.0
        interval = 3.0

        while elapsed < timeout:
            await asyncio.sleep(interval)
            elapsed += interval

            res = await lk_api.egress.list_egress(api.ListEgressRequest(egress_id=egress_id))
            if res.items:
                info = res.items[0]
                status = info.status
                if status == api.EgressStatus.EGRESS_COMPLETE:
                    logger.info(f"Recording completed: egress_id={egress_id}")
                    await lk_api.aclose()
                    return True
                elif status in (api.EgressStatus.EGRESS_FAILED, api.EgressStatus.EGRESS_ABORTED):
                    logger.error(f"Recording failed: egress_id={egress_id} status={status}")
                    await lk_api.aclose()
                    return False

        logger.warning(f"Recording timed out after {timeout}s: egress_id={egress_id}")
        await lk_api.aclose()
        return False

    except Exception as e:
        logger.error(f"Error polling egress {egress_id}: {e}")
        return False
