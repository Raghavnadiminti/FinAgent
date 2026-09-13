import asyncio

from google.adk.runners import InMemoryRunner
from google.genai import types
from agent import orchestrator_agent as root_agent

from dotenv import load_dotenv

load_dotenv()

async def main():
    runner = InMemoryRunner(
        agent=root_agent,
        app_name="ai_accountant",
    )

    user_id = "test_user"
    session_id = "test_session"

    # Create a session
    await runner.session_service.create_session(
        app_name="ai_accountant",
        user_id=user_id,
        session_id=session_id,
    )

    prompt = "What is the profit and loss for August of every year?"

    print("\n" + "=" * 60)
    print("AI ACCOUNTANT")
    print("=" * 60)
    print(f"\nUser: {prompt}\n")
    print("Assistant:\n")

    content = types.Content(
        role="user",
        parts=[
            types.Part(text=prompt)
        ],
    )

    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=content,
    ):
        if event.is_final_response():
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        print(part.text)


if __name__ == "__main__":
    asyncio.run(main())