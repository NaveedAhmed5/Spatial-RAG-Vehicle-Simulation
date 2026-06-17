import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate

# ==============================================================================
# ENVIRONMENT SETUP
# ==============================================================================
dotenv_path = os.path.join(os.path.dirname(__file__), "../.env")
load_dotenv(dotenv_path=dotenv_path)

api_key = os.environ.get("GROQ_API_KEY")
if not api_key:
    raise ValueError("GROQ_API_KEY is missing. Ensure the .env file is present in the root directory.")

# ==============================================================================
# LLM INITIALIZATION & DETERMINISTIC CONSTRAINTS (Task 3.1 & 3.2)
# ==============================================================================
# Initialize ChatGroq with low-latency and deterministic settings
raw_llm = ChatGroq(
    model="llama-3.1-8b-instant",
    temperature=0,
    groq_api_key=api_key
)

# Apply a JSON Schema to .with_structured_output() to enforce a dictionary return type.
# This ensures LangChain strictly returns the exact JSON format natively.
action_schema = {
    "title": "DriverAction",
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["MOVE_LEFT", "MOVE_RIGHT", "STAY"],
            "description": "The maneuver to take based on the hazard detections."
        }
    },
    "required": ["action"]
}
structured_llm = raw_llm.with_structured_output(action_schema)

# ==============================================================================
# TASK CONTEXT COMPILER (Task 3.3)
# ==============================================================================
# Strict prompt instructing the AI on how to interpret radar and lane data
PROMPT_TEMPLATE = """You are an autonomous driving agent navigating a highway.
Your objective is to navigate safely by analyzing your current lane and upcoming radar detections.

RULES:
1. There are exactly 3 lanes: 1 (Left), 2 (Center), and 3 (Right).
2. If there is a hazard in your current lane, you MUST maneuver to an adjacent clear lane.
3. If your current lane is clear of hazards, you SHOULD STAY in your current lane to maintain stability.
4. You must select one of the following maneuvers: "MOVE_LEFT", "MOVE_RIGHT", or "STAY".

Current State:
- Current Lane: {current_lane}
- Radar Data (Upcoming Hazards): {radar_data}

You must strictly respond with a single JSON dictionary containing exactly one key "action".
Do not provide any explanations or extra markdown text.
Example format: {{"action": "STAY"}}
"""

prompt = PromptTemplate(
    template=PROMPT_TEMPLATE,
    input_variables=["current_lane", "radar_data"]
)

# ==============================================================================
# CHAIN ASSEMBLY
# ==============================================================================
# Combine the prompt and the structured LLM using the LangChain pipe operator
ai_driver_chain = prompt | structured_llm

# ==============================================================================
# VERIFICATION BLOCK
# ==============================================================================
if __name__ == "__main__":
    print("--- Phase 3.2/3.3: AI Driver Chain Sanity Check ---")
    try:
        # Mocking a scenario where the car is in Lane 2 (Center)
        # Radar detects a blockade exactly in our path
        mock_state = {
            "current_lane": 2,
            "radar_data": "Hazard detected in Lane 2 at Y=400"
        }
        
        print("\nInvoking AI Driver Chain...")
        print(f"Mock Input State: {mock_state}")
        
        # Invoke the chain
        result = ai_driver_chain.invoke(mock_state)
        
        # Validate the output is a parsed dictionary
        print(f"\n[Output Type]: {type(result)}")
        print(f"[Parsed Output]: {result}")
        
        if isinstance(result, dict) and "action" in result:
            print("\n✅ Verification Passed: AI successfully returned a structured Python dictionary with an action.")
        else:
            print("\n⚠️ Verification Failed: The output did not meet the structured dictionary criteria.")
            
    except Exception as e:
        print(f"\n❌ Execution Error: {e}")
