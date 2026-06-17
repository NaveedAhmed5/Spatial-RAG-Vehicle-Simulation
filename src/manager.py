from typing import TypedDict, List, Union
from langgraph.graph import StateGraph, START, END

# Import our custom dependencies from adjacent files
from database import SpatialMemoryDB
from agent import ai_driver_chain

# Initialize a default memory database so the module can run standalone.
# Note: Because this is an in-memory client, it is empty by default.
# I've added a `db_override` parameter to `get_ai_decision` so that `main.py`
# can pass the populated engine database into this graph later!
global_db = SpatialMemoryDB()

# ==============================================================================
# 1. State Schema
# ==============================================================================
class State(TypedDict):
    current_lane: int
    car_y: float
    radar_data: Union[List, str]
    action: str

# ==============================================================================
# 2. Nodes
# ==============================================================================
def sensor_node(state: State) -> State:
    """
    Node 1 (Sensor Node):
    Acts as a passthrough to confirm `current_lane` and `car_y` 
    are securely loaded into the state from the external game loop.
    """
    # LangGraph automatically merges dictionary returns into the state
    return {
        "current_lane": state["current_lane"], 
        "car_y": state["car_y"]
    }

def radar_node(state: State) -> State:
    """
    Node 2 (Radar Node):
    Queries the spatial memory database for upcoming hazards 
    and updates the state with the findings.
    """
    car_y = state["car_y"]
    
    # Query Qdrant for obstacles 200px to 400px ahead
    hazards = global_db.get_upcoming_hazards(car_y)
    
    # Format the results into a highly readable string for the LLM prompt
    if not hazards:
        radar_summary = "Clear road ahead. No upcoming hazards detected."
    else:
        radar_summary = f"Detected {len(hazards)} hazards ahead: {hazards}"
        
    return {"radar_data": radar_summary}

def agent_node(state: State) -> State:
    """
    Node 3 (Agent Node):
    Passes the lane and radar data to the Groq LLM chain, extracting 
    the exact action string ("MOVE_LEFT", "MOVE_RIGHT", or "STAY").
    """
    # Prepare the context dictionary expected by our PromptTemplate
    chain_input = {
        "current_lane": state["current_lane"],
        "radar_data": state["radar_data"]
    }
    
    # Invoke the compiled LangChain (returns a dictionary due to our structured wrapper)
    result = ai_driver_chain.invoke(chain_input)
    
    # Extract the exact string action
    chosen_action = result.get("action", "STAY")
    
    return {"action": chosen_action}

# ==============================================================================
# 3. Build and Compile the Graph
# ==============================================================================
# Initialize the state graph
builder = StateGraph(State)

# Add the nodes
builder.add_node("sensor", sensor_node)
builder.add_node("radar", radar_node)
builder.add_node("agent", agent_node)

# Add linear edges connecting them: START -> Sensor -> Radar -> Agent -> END
builder.add_edge(START, "sensor")
builder.add_edge("sensor", "radar")
builder.add_edge("radar", "agent")
builder.add_edge("agent", END)

# Compile the graph into an executable application
app = builder.compile()

# ==============================================================================
# 4. Public Interface
# ==============================================================================
def get_ai_decision(current_lane: int, car_y: float, db_override=None) -> str:
    """
    Wrapper function to invoke the compiled LangGraph execution.
    This is the clean public interface that `src/main.py` will call.
    
    db_override: Allows the main script to pass the engine's populated 
                 SpatialMemoryDB instance into the graph.
    """
    global global_db
    if db_override is not None:
        global_db = db_override

    # Define the initial state
    initial_state = {
        "current_lane": current_lane,
        "car_y": car_y
    }
    
    # Execute the graph synchronously
    final_state = app.invoke(initial_state)
    
    # Return ONLY the final string action
    return final_state.get("action", "STAY")

# ==============================================================================
# VERIFICATION BLOCK
# ==============================================================================
if __name__ == "__main__":
    print("--- Phase 3.4: LangGraph Manager Sanity Check ---")
    
    import uuid
    # Inject a mock hazard into our local database to test the radar node properly
    global_db.log_hazard(lane=2, y_position=400, hazard_type="blockage", hazard_id=str(uuid.uuid4()))
    
    print("\nSimulating a LangGraph loop...")
    print("State: Car is at Y=500 in Lane 2. Hazard logged at Y=400 in Lane 2.")
    
    # Run the graph
    decision = get_ai_decision(current_lane=2, car_y=500)
    
    print(f"\n[Final Graph Output]: {decision}")
    
    if decision in ["MOVE_LEFT", "MOVE_RIGHT", "STAY"]:
        print("✅ Verification Passed: LangGraph successfully routed data and extracted the string maneuver.")
    else:
        print("⚠️ Verification Failed: The graph did not return a valid maneuver string.")
