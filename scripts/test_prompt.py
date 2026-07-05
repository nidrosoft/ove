"""Smoke test: the system prompt must build without raising.

A single unescaped {placeholder} inside the f-string in agent/prompts.py
crashes EVERY incoming call (NameError at agent init → job crashed → the
phone rings forever). This caught exactly that bug on 2026-07-05.

Run: python -m scripts.test_prompt   (also run in the Docker build)
"""
import sys

from agent.config import PracticeConfig
from agent.prompts import build_system_prompt


def main() -> int:
    configs = {
        "defaults": PracticeConfig(),
        "populated": PracticeConfig(
            practice_id="test-practice",
            practice_name="Test Dental",
            practice_phone="+18582505610",
            practice_timezone="America/Los_Angeles",
            practice_hours="Mon-Fri 8am-5pm",
            practice_address="123 Main St, San Diego, CA",
            agent_name="Relay",
            knowledge_base="Sample knowledge base text.",
            providers=[{"name": "Dr. Smith", "title": "Dentist", "specialties": "General"}],
            services=["Cleaning", "Checkup"],
        ),
    }
    caller_infos = {
        "anonymous": None,
        "recognized": {
            "phone_number": "+16195551234",
            "is_known_patient": True,
            "patient_name": "Sarah J",
            "last_visit": "2026-06-01",
            "upcoming_appointments": "None",
            "preferred_provider": "Dr. Smith",
        },
    }

    failures = 0
    for cfg_name, cfg in configs.items():
        for ci_name, ci in caller_infos.items():
            try:
                prompt = build_system_prompt(cfg, caller_info=ci)
                assert len(prompt) > 1000, "prompt suspiciously short"
                print(f"OK   config={cfg_name} caller={ci_name} len={len(prompt)}")
            except Exception as e:
                failures += 1
                print(f"FAIL config={cfg_name} caller={ci_name}: {type(e).__name__}: {e}")

    if failures:
        print(f"\n{failures} prompt build(s) FAILED — do not deploy.")
        return 1
    print("\nAll prompt builds passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
