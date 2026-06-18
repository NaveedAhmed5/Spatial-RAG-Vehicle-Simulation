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
PROMPT_TEMPLATE = """You are an autonomous driving agent controlling a car on a 3-lane highway.

LANE NUMBERING (critical — memorize this):
  Lane 1 = LEFT lane
  Lane 2 = CENTER lane  
  Lane 3 = RIGHT lane

ACTION DEFINITIONS (critical — memorize this):
  MOVE_LEFT  = decrease your lane number by 1 (Lane 2 → Lane 1, Lane 3 → Lane 2)
  MOVE_RIGHT = increase your lane number by 1 (Lane 1 → Lane 2, Lane 2 → Lane 3)
  STAY       = remain in your current lane

BOUNDARY RULES:
  - If you are in Lane 1, MOVE_LEFT is forbidden (you are at the edge).
  - If you are in Lane 3, MOVE_RIGHT is forbidden (you are at the edge).

RADAR DATA:
The radar shows hazards that are approaching your car. Each entry tells you which lane number
contains a hazard and how far away it is.

YOUR CURRENT STATE:
  Current Lane: {current_lane}
  Radar Data: {radar_data}

DECISION LOGIC — follow these steps in order:
  Step 1: Does the radar show a hazard in Lane {current_lane}?
    YES → You MUST move to a clear adjacent lane. Choose MOVE_LEFT or MOVE_RIGHT.
          IMPORTANT: First calculate which lane you would land in, then verify that lane 
          has NO hazard before committing to that action.
    NO  → The road ahead in your lane is clear. Output STAY.

  Step 2 (only if Step 1 says move): Which direction is safe?
    - MOVE_LEFT would put you in Lane {current_lane} - 1. Is that lane clear of hazards? If yes, choose MOVE_LEFT.
    - MOVE_RIGHT would put you in Lane {current_lane} + 1. Is that lane clear of hazards? If yes, choose MOVE_RIGHT.
    - If BOTH directions are blocked, choose the direction that is further from any hazard.

Now output EXACTLY one JSON object with no explanation:
{{"action": "MOVE_LEFT"}} or {{"action": "MOVE_RIGHT"}} or {{"action": "STAY"}}
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
