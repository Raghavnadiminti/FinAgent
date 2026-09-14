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
    session_id = "accounting_session"

    await runner.session_service.create_session(
        app_name="ai_accountant",
        user_id=user_id,
        session_id=session_id,
    )

    while True:

        prompt = input("\nYou: ")

        if prompt.lower() in {"exit", "quit"}:
            break

        message = types.Content(
            role="user",
            parts=[
                types.Part(text=prompt)
            ],
        )

        print("\nAI Accountant: ", end="")

        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=message,
        ):

            if event.is_final_response():

                if event.content and event.content.parts:

                    for part in event.content.parts:

                        if part.text:
                            print(part.text)
if __name__ == "__main__":
    asyncio.run(main())