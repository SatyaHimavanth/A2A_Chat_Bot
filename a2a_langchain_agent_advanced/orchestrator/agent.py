from google.adk.models.lite_llm import LiteLlm
from google.adk.agents import LlmAgent

from google.adk.agents.remote_a2a_agent import AGENT_CARD_WELL_KNOWN_PATH
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from google.adk.agents.llm_agent import LlmAgent
from google.adk.tools import load_memory
from google.adk.tools.tool_context import ToolContext
from google.adk.a2a.utils.agent_to_a2a import to_a2a
import os
import uvicorn

from dotenv import load_dotenv
load_dotenv()


model_name = "azure/gpt-4.1"
try:
    model = LiteLlm(model=model_name)
    print(f"using model '{model}'.")
except Exception as e:
    print(f"Error: {e}")

# master is running on 8081

calculator_agent = RemoteA2aAgent(
    name="calculator_agent",
    description="a specialized assistant for math calculations",
    agent_card=(
        f"http://localhost:10000/{AGENT_CARD_WELL_KNOWN_PATH}"
    ),
)


root_agent = LlmAgent(
    name="master_agent",
    # model="gemini-2.5-flash",
    model=LiteLlm(model=model_name),
    instruction="""
        You are the Master Agent
        you delegate to your sub agents by the a2a protocol

    """,
    sub_agents=[calculator_agent]
)

if __name__ == "__main__":
    a2a_app = to_a2a(root_agent, port=8081)
    # Use host='0.0.0.0' to allow external access.
    uvicorn.run(a2a_app, host="0.0.0.0", port=8081)