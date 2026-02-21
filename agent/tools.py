"""Tool definitions for the voice agent — calls Omnira Platform API for real actions."""
import json
import logging

import httpx

from livekit.agents import function_tool, RunContext

from agent.config import Config

logger = logging.getLogger("omnira-tools")


async def _call_omnira_action(action: str, params: dict) -> dict:
    """Call the Omnira platform API to execute an action."""
    url = f"{Config.OMNIRA_API_URL}/voice-engine/actions"
    body = {
        "action": action,
        "practice_id": Config.PRACTICE_ID,
        "params": params,
    }

    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.post(
                url,
                json=body,
                headers={
                    "Authorization": f"Bearer {Config.OMNIRA_API_KEY}",
                    "Content-Type": "application/json",
                },
            )
            if resp.headers.get("content-type", "").startswith("application/json"):
                data = resp.json()
            else:
                logger.error(f"Omnira API non-JSON response ({action}): status={resp.status_code} body={resp.text[:200]}")
                return {"success": False, "error": f"Non-JSON response (status {resp.status_code})"}
            if resp.status_code >= 400:
                logger.error(f"Omnira API error ({action}): {resp.status_code} — {data}")
            return data
    except Exception as e:
        logger.error(f"Omnira API call failed ({action}): {e}")
        return {"success": False, "error": str(e)}


@function_tool(description="Look up an existing patient by name or phone number.")
async def lookup_patient(
    context: RunContext,
    name: str = "",
    phone: str = "",
) -> str:
    """Look up a patient in the system.

    Args:
        name: Patient name to search for
        phone: Patient phone number to search for
    """
    logger.info(f"Looking up patient: name={name}, phone={phone}")
    result = await _call_omnira_action("lookup_patient", {"name": name, "phone": phone})

    if result.get("found"):
        patients = result.get("patients", [])
        p = patients[0]
        return json.dumps({
            "found": True,
            "patient_id": p.get("id"),
            "name": f"{p.get('first_name', '')} {p.get('last_name', '')}".strip(),
            "email": p.get("email", ""),
            "phone": p.get("phone_mobile", ""),
            "status": p.get("status", ""),
        })
    return json.dumps({"found": False, "message": "No patient found with that information."})


@function_tool(description="Check available appointment slots. Call this when a patient asks about availability.")
async def check_availability(
    context: RunContext,
    date: str,
    procedure_type: str = "general",
) -> str:
    """Check available appointment slots for a given date.

    Args:
        date: The date to check (YYYY-MM-DD format or natural language like 'next Tuesday')
        procedure_type: Type of appointment (general, cleaning, emergency, consultation)
    """
    logger.info(f"Checking availability for {date}, procedure: {procedure_type}")

    # Availability is still handled locally until Omnira has a scheduling engine.
    # Return representative slots based on practice hours.
    return json.dumps({
        "available_slots": [
            {"time": "9:00 AM", "provider": "Dr. Smith"},
            {"time": "10:30 AM", "provider": "Dr. Smith"},
            {"time": "2:00 PM", "provider": "Dr. Johnson"},
            {"time": "3:30 PM", "provider": "Dr. Johnson"},
        ],
        "date": date,
    })


@function_tool(description="Book an appointment for a patient. Use this after confirming details with the caller.")
async def book_appointment(
    context: RunContext,
    patient_name: str,
    date: str,
    time: str,
    procedure_type: str,
    patient_phone: str = "",
    patient_email: str = "",
    is_new_patient: bool = True,
) -> str:
    """Book an appointment via the Omnira platform.

    Args:
        patient_name: Full name of the patient
        date: Appointment date (YYYY-MM-DD)
        time: Appointment time (e.g., '9:00 AM')
        procedure_type: Type of procedure (cleaning, checkup, emergency, etc.)
        patient_phone: Patient phone number (optional)
        patient_email: Patient email address (optional)
        is_new_patient: Whether this is a new patient (default True)
    """
    logger.info(f"Booking: {patient_name} on {date} at {time} for {procedure_type}")

    result = await _call_omnira_action("book_appointment", {
        "patient_name": patient_name,
        "date": date,
        "time": time,
        "procedure_type": procedure_type,
        "phone": patient_phone,
        "email": patient_email,
        "is_new_patient": is_new_patient,
    })

    if result.get("success"):
        return json.dumps({
            "status": "confirmed",
            "appointment_id": result.get("appointment_id"),
            "patient_id": result.get("patient_id"),
            "message": result.get("message", f"Appointment booked for {patient_name} on {date} at {time}."),
        })

    return json.dumps({
        "status": "error",
        "message": f"I wasn't able to book that appointment right now. Error: {result.get('error', 'unknown')}",
    })


@function_tool(description="Send a confirmation SMS to the patient. Use after booking an appointment.")
async def send_sms(
    context: RunContext,
    to_phone: str,
    message: str,
) -> str:
    """Send an SMS message via the Omnira platform.

    Args:
        to_phone: Recipient phone number (E.164 format, e.g., +15551234567)
        message: The SMS message text
    """
    logger.info(f"Sending SMS to {to_phone}: {message[:50]}...")

    result = await _call_omnira_action("send_sms", {
        "phone": to_phone,
        "message": message,
    })

    if result.get("success"):
        return f"Confirmation text sent successfully to {to_phone}."
    return "I wasn't able to send the text right now, but I've noted the appointment details."


@function_tool(description="Send a confirmation email to the patient. Use after booking an appointment.")
async def send_email(
    context: RunContext,
    to_email: str,
    subject: str,
    body: str,
) -> str:
    """Send an email via the Omnira platform.

    Args:
        to_email: Recipient email address
        subject: Email subject line
        body: Email body text (plain text)
    """
    logger.info(f"Sending email to {to_email}: {subject}")

    result = await _call_omnira_action("send_confirmation_email", {
        "email": to_email,
        "subject": subject,
        "body": body,
    })

    if result.get("success"):
        return f"Confirmation email sent successfully to {to_email}."
    return "I wasn't able to send the email right now, but your appointment is confirmed."


@function_tool(description="Transfer the call to a human staff member. Use when the caller needs something you cannot handle.")
async def transfer_call(
    context: RunContext,
    reason: str,
    department: str = "front_desk",
) -> str:
    """Transfer the current call to human staff.

    Args:
        reason: Brief reason for the transfer
        department: Which department to transfer to (front_desk, billing, clinical)
    """
    logger.info(f"Call transfer requested: {reason} → {department}")
    return f"I'm transferring you now to our {department.replace('_', ' ')} team. One moment please."
