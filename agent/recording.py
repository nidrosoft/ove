"""Call recording via LiveKit Egress API → Supabase Storage.

Uses Supabase Storage's S3-compatible endpoint with session token auth:
  access_key = Supabase project ref
  secret     = Supabase anon key
  session    = Supabase service role key (bypasses RLS)
"""
import logging
import os

from livekit import api

logger = logging.getLogger("omnira-recording")

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
RECORDING_BUCKET = "call-recordings"


def _get_project_ref() -> str:
    if not SUPABASE_URL:
        return ""
    return SUPABASE_URL.replace("https://", "").split(".")[0]


def _get_s3_endpoint() -> str:
    ref = _get_project_ref()
    if not ref:
        return ""
    return f"https://{ref}.supabase.co/storage/v1/s3"


def _is_configured() -> bool:
    return bool(SUPABASE_URL and SUPABASE_ANON_KEY and SUPABASE_SERVICE_KEY)


async def start_room_recording(room_name: str, call_id: str) -> str | None:
    """Start an audio-only room composite egress uploading to Supabase Storage.

    Returns the egress_id if successful, None otherwise.
    """
    if not _is_configured():
        logger.warning("Supabase credentials not configured — skipping recording")
        return None

    endpoint = _get_s3_endpoint()
    project_ref = _get_project_ref()

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
                        access_key=project_ref,
                        secret=SUPABASE_ANON_KEY,
                        session_token=SUPABASE_SERVICE_KEY,
                        region="us-east-1",
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
    ref = _get_project_ref()
    if not ref:
        return ""
    return f"https://{ref}.supabase.co/storage/v1/object/public/{RECORDING_BUCKET}/{call_id}.ogg"


async def wait_for_egress(egress_id: str, timeout: float = 60.0) -> bool:
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
                    error_msg = getattr(info, 'error', 'unknown')
                    logger.error(f"Recording failed: egress_id={egress_id} status={status} error={error_msg}")
                    await lk_api.aclose()
                    return False
                logger.info(f"Recording egress status: {status} (elapsed={elapsed:.0f}s)")

        logger.warning(f"Recording timed out after {timeout}s: egress_id={egress_id}")
        try:
            await lk_api.egress.stop_egress(api.StopEgressRequest(egress_id=egress_id))
        except Exception:
            pass
        await lk_api.aclose()
        return False

    except Exception as e:
        logger.error(f"Error polling egress {egress_id}: {e}")
        return False
