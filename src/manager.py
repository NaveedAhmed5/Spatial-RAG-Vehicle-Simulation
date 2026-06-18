from typing import TypedDict, List, Union
from langgraph.graph import StateGraph, START, END

# Import our custom dependencies from adjacent files
from database import SpatialMemoryDB
# from agent import ai_driver_chain

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
    policy: dict

# ==============================================================================
# 2. Nodes
# ==============================================================================
def sensor_node(state: State) -> State:
    return {
        "current_lane": state["current_lane"], 
        "car_y": state["car_y"]
    }

def radar_node(state: State) -> State:
    car_y = state["car_y"]
    if state.get("radar_data"):
        return {"radar_data": state["radar_data"]}
    
    hazards = global_db.get_upcoming_hazards(car_y)
    if not hazards:
        radar_summary = "Clear road ahead. No upcoming hazards detected in any lane."
    else:
        hazard_descriptions = []
        for h in hazards:
            dist = int(car_y - h['y_position'])
            hazard_descriptions.append(f"Lane {h['lane']} has a {h['hazard_type']} {dist}px ahead")
        radar_summary = "; ".join(hazard_descriptions)
        
    return {"radar_data": radar_summary}

from langchain_core.messages import HumanMessage
import json

def agent_node(state: State) -> State:
    from agent import get_agent
    ai_driver_agent = get_agent()
    
    human_msg = f"My Current Lane: {state['current_lane']}\nHazards Detected Ahead: {state['radar_data']}"
    result = ai_driver_agent.invoke({"messages": [HumanMessage(content=human_msg)]})
    final_text = result["messages"][-1].content
    
    try:
        parsed = json.loads(final_text)
        chosen_policy = parsed if "strategy" in parsed else {"strategy": "CAUTIOUS", "preferred_lane": 2}
    except Exception as e:
        print(f"[JSON Parse Error] Could not parse ReAct output: {final_text}")
        chosen_policy = {"strategy": "CAUTIOUS", "preferred_lane": 2}
    
    return {"policy": chosen_policy}

# ==============================================================================
# 3. Build and Compile the Graph
# ==============================================================================
builder = StateGraph(State)
builder.add_node("sensor", sensor_node)
builder.add_node("radar", radar_node)
builder.add_node("agent", agent_node)
builder.add_edge(START, "sensor")
builder.add_edge("sensor", "radar")
builder.add_edge("radar", "agent")
builder.add_edge("agent", END)
app = builder.compile()

# ==============================================================================
# 4. Public Interface & Reflex Engine
# ==============================================================================
def get_ai_decision(current_lane: int, car_y: float, db_override=None, radar_data_override: str = None) -> dict:
    global global_db
    if db_override is not None:
        global_db = db_override

    initial_state = {
        "current_lane": current_lane,
        "car_y": car_y,
        "radar_data": radar_data_override or ""
    }
    
    final_state = app.invoke(initial_state)
    return final_state.get("policy", {"strategy": "CAUTIOUS", "preferred_lane": 2})

def calculate_safe_maneuver(current_lane: int, obstacles: list, car_y: float, policy: dict) -> dict:
    """
    The deterministic Python Reflex Engine.
    Runs at 60 FPS. Instantly calculates dodges based on exact math and current policy.
    obstacles: list of live engine Obstacle objects.
    """
    strategy = policy.get("strategy", "CAUTIOUS")
    preferred_lane = policy.get("preferred_lane", 2)
    
    dodge_threshold = 92 if strategy == "AGGRESSIVE" else 200
    CRITICAL_THRESHOLD = 92 # We MUST dodge if closer than this
    
    current_lane_obstacles = [obs for obs in obstacles if obs.lane == current_lane and obs.y < car_y + 40]
    
    if not current_lane_obstacles:
        if current_lane != preferred_lane:
            pref_obs = [obs for obs in obstacles if obs.lane == preferred_lane and obs.y > car_y - dodge_threshold and obs.y < car_y + 80]
            if not pref_obs:
                action = "MOVE_LEFT" if preferred_lane < current_lane else "MOVE_RIGHT"
                return {"action": action, "delay_ms": 0}
        return {"action": "STAY", "delay_ms": 0}
        
    closest_obs = max(current_lane_obstacles, key=lambda o: o.y)
    dist_to_obs = car_y - closest_obs.y
    
    # Do we NEED to dodge?
    if dist_to_obs <= dodge_threshold:
        adjacent_lanes = []
        if current_lane > 1: adjacent_lanes.append(current_lane - 1)
        if current_lane < 3: adjacent_lanes.append(current_lane + 1)
        
        lane_safety = {}
        for l in adjacent_lanes:
            obs_in_l = [obs for obs in obstacles if obs.lane == l and obs.y < car_y + 80]
            if not obs_in_l:
                lane_safety[l] = 9999 
            else:
                closest_l_obs = max(obs_in_l, key=lambda o: o.y)
                lane_safety[l] = car_y - closest_l_obs.y
                
        best_lane = max(lane_safety, key=lane_safety.get)
        best_safety_dist = lane_safety[best_lane]
        
        # Hysteresis: Don't dodge unless the target lane is significantly safer, OR we are critically close
        if best_safety_dist > dist_to_obs + 50 or dist_to_obs <= CRITICAL_THRESHOLD:
            
            # Perfect slide check: is there an obstacle directly next to us?
            if best_safety_dist > -80 and best_safety_dist < 80:
                # Yes, wait for it to pass.
                return {"action": "STAY", "delay_ms": 0}
                
            action = "MOVE_LEFT" if best_lane < current_lane else "MOVE_RIGHT"
            return {"action": action, "delay_ms": 0}
            
    return {"action": "STAY", "delay_ms": 0}

# ==============================================================================
# VERIFICATION BLOCK
# ==============================================================================
if __name__ == "__main__":
    print("--- Phase 3.4: LangGraph Manager Sanity Check ---")
    
    import uuid
    global_db.log_hazard(lane=2, y_position=400, hazard_type="blockage", hazard_id=str(uuid.uuid4()))
    
    print("\nSimulating a LangGraph loop...")
    decision = get_ai_decision(current_lane=2, car_y=500)
    
    print(f"\n[Final Graph Output]: {decision}")
    
    if isinstance(decision, dict) and "strategy" in decision:
        print("✅ Verification Passed: LangGraph successfully returned a strategic policy.")
    else:
        print("⚠️ Verification Failed: The graph did not return a valid policy dictionary.")
