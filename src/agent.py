import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, SystemMessage

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
llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0,
    groq_api_key=api_key
)

# ==============================================================================
# TASK CONTEXT COMPILER (Task 3.3)
# ==============================================================================
SYSTEM_PROMPT = """You are the Strategic Commander for an autonomous car.
The car's internal Python engine handles millisecond dodging and reflexes. Your job is to set the HIGH-LEVEL PLAYSTYLE POLICY based on the radar snapshot.

LANE NUMBERING:
  Lane 1 = LEFT lane
  Lane 2 = CENTER lane  
  Lane 3 = RIGHT lane

DECISION LOGIC:
1. Analyze the Hazards Detected string. 
2. Determine which lane has the MOST obstacles, or the CLOSEST obstacles. That lane is dangerous.
3. Determine which lane is the SAFEST (fewest or furthest obstacles).
4. Set a "strategy":
   - "AGGRESSIVE": The car will dodge at the last possible second. (Use this if the road is mostly clear).
   - "CAUTIOUS": The car will dodge early and prioritize empty lanes. (Use this if the road is congested).
5. Set a "preferred_lane": 1, 2, or 3. The reflex engine will default to this lane when possible.

FINAL OUTPUT:
Your FINAL response MUST be EXACTLY one JSON object containing the policy. Do not include markdown.

Example:
{"strategy": "CAUTIOUS", "preferred_lane": 3, "rationale": "Lanes 1 and 2 are highly congested with close blockages."}
"""

# ==============================================================================
# AGENT INITIALIZATION
# ==============================================================================
def get_agent():
    """
    Initializes and returns the LangGraph Strategic Commander.
    Uses the LLM to analyze the Qdrant radar snapshot and output a Playstyle Policy.
    """
    ai_driver_agent = create_react_agent(
        llm,
        tools=[],
        prompt=SystemMessage(content=SYSTEM_PROMPT)
    )
    return ai_driver_agent

# ==============================================================================
# VERIFICATION BLOCK
# ==============================================================================
if __name__ == "__main__":
    print("--- Phase 3.2/3.3: AI Driver ReAct Agent Sanity Check ---")
    try:
        ai_driver_agent = get_agent()
        # Mocking a scenario where the car is in Lane 2 (Center)
        # Radar detects a blockade exactly in our path
        human_msg = "My Current Lane: 1\nHazards Detected Ahead: Lane 1 has a blockage 300px ahead; Lane 2 has a blockage 25px ahead"
        
        print("\nInvoking AI Driver ReAct Agent...")
        print(f"Mock Input State: {human_msg}")
        
        # Invoke the chain
        result = ai_driver_agent.invoke({"messages": [HumanMessage(content=human_msg)]})
        
        final_text = result["messages"][-1].content
        
        print(f"\n[Final Output]: {final_text}")
        
        import json
        parsed = json.loads(final_text)
        
        if isinstance(parsed, dict) and "strategy" in parsed and "preferred_lane" in parsed:
            print("\n[OK] Verification Passed: AI successfully returned a structured Python dictionary with a 'strategy'.")
        else:
            print("\n[WARN] Verification Failed: The output did not meet the structured dictionary criteria.")
            
    except Exception as e:
        print(f"\n[ERROR] Execution Error: {e}")
