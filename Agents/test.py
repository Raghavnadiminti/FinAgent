import asyncio
import os

from dotenv import load_dotenv
from google.adk.runners import InMemoryRunner
from google.genai import types

from analytics_agent import root_agent


load_dotenv()




# ============================================================
# EXAMPLE PROMPT
# ============================================================

EXAMPLE_PROMPT = """
What was our net profit for August 2026?
Also tell me the total revenue and total expenses.
"""


# ============================================================
# RUN AGENT
# ============================================================

async def main():

    runner = InMemoryRunner(
        agent=root_agent,
        app_name="ai_accountant",
    )

    user_id = "test_user"
    session_id = "analytics_test_session"

    # Create session
    await runner.session_service.create_session(
        app_name="ai_accountant",
        user_id=user_id,
        session_id=session_id,
    )

    message = types.Content(
        role="user",
        parts=[
            types.Part(
                text=EXAMPLE_PROMPT
            )
        ],
    )

    print("\n" + "=" * 60)
    print("ANALYTICS AGENT")
    print("=" * 60)

    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=message,
    ):

        # Only print actual text responses
        if event.content and event.content.parts:

            for part in event.content.parts:

                if part.text:
                    print(part.text)

    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())



