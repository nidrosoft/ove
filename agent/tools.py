"""Tool definitions for the voice agent — these are the actions it can take during a call."""
import json
import logging

import httpx
import resend
from twilio.rest import Client as TwilioClient

from livekit.agents import function_tool, RunContext

from agent.config import Config

logger = logging.getLogger("omnira-tools")

# Initialize clients
twilio_client = TwilioClient(Config.TWILIO_ACCOUNT_SID, Config.TWILIO_AUTH_TOKEN) if Config.TWILIO_ACCOUNT_SID else None
resend.api_key = Config.RESEND_API_KEY


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
    # TODO: Replace with real Omnira/Stella API call
    # For MVP, return mock availability
    logger.info(f"Checking availability for {date}, procedure: {procedure_type}")

    # Mock response — replace with actual API call:
    # async with httpx.AsyncClient() as client:
    #     resp = await client.get(f"{Config.OMNIRA_API_URL}/availability",
    #         params={"date": date, "procedure": procedure_type},
    #         headers={"Authorization": f"Bearer {Config.OMNIRA_API_KEY}"})
    #     return resp.text

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
) -> str:
    """Book an appointment.

    Args:
        patient_name: Full name of the patient
        date: Appointment date (YYYY-MM-DD)
        time: Appointment time (e.g., '9:00 AM')
        procedure_type: Type of procedure (cleaning, checkup, emergency, etc.)
        patient_phone: Patient phone number (optional)
        patient_email: Patient email address (optional)
    """
    logger.info(f"Booking: {patient_name} on {date} at {time} for {procedure_type}")

    # TODO: Replace with real Omnira/Stella API call
    # async with httpx.AsyncClient() as client:
    #     resp = await client.post(f"{Config.OMNIRA_API_URL}/appointments",
    #         json={"patient_name": patient_name, "date": date, "time": time,
    #               "procedure": procedure_type, "phone": patient_phone, "email": patient_email},
    #         headers={"Authorization": f"Bearer {Config.OMNIRA_API_KEY}"})
    #     return resp.text

    return json.dumps({
        "status": "confirmed",
        "appointment_id": "APT-2026-001",
        "patient_name": patient_name,
        "date": date,
        "time": time,
        "procedure": procedure_type,
        "message": f"Appointment booked for {patient_name} on {date} at {time} for {procedure_type}."
    })


@function_tool(description="Send a confirmation SMS to the patient. Use after booking an appointment.")
async def send_sms(
    context: RunContext,
    to_phone: str,
    message: str,
) -> str:
    """Send an SMS message via Twilio.

    Args:
        to_phone: Recipient phone number (E.164 format, e.g., +15551234567)
        message: The SMS message text
    """
    logger.info(f"Sending SMS to {to_phone}: {message[:50]}...")

    if not twilio_client:
        return "SMS service not configured. Message noted for staff follow-up."

    try:
        msg = twilio_client.messages.create(
            body=message,
            from_=Config.TWILIO_PHONE_NUMBER,
            to=to_phone,
        )
        return f"Confirmation text sent successfully to {to_phone}."
    except Exception as e:
        logger.error(f"SMS failed: {e}")
        return "I wasn't able to send the text right now, but I've noted the appointment details."


@function_tool(description="Send a confirmation email to the patient. Use after booking an appointment.")
async def send_email(
    context: RunContext,
    to_email: str,
    subject: str,
    body: str,
) -> str:
    """Send an email via Resend.

    Args:
        to_email: Recipient email address
        subject: Email subject line
        body: Email body text (plain text)
    """
    logger.info(f"Sending email to {to_email}: {subject}")

    if not Config.RESEND_API_KEY:
        return "Email service not configured. Message noted for staff follow-up."

    try:
        email = resend.Emails.send({
            "from": Config.FROM_EMAIL,
            "to": [to_email],
            "subject": subject,
            "text": body,
        })
        return f"Confirmation email sent successfully to {to_email}."
    except Exception as e:
        logger.error(f"Email failed: {e}")
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
    # In production, this would trigger a LiveKit SIP transfer
    # For now, return a message
    return f"I'm transferring you now to our {department.replace('_', ' ')} team. One moment please."
