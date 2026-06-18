import pygame
import sys
import threading
import queue

# 1. Component Imports
# Import our standalone physical game engine and its frame rate
from engine import Engine, FPS
# Import the LangGraph routing manager
from manager import get_ai_decision

class SimulationBridge:
    """
    The Asynchronous Event Bridge.
    This class wraps the Pygame 60Hz loop and orchestrates 
    the asynchronous handoff to the 2Hz LangGraph LLM network request.
    """
    def __init__(self):
        # Initialize the Physical Engine
        self.engine = Engine()
        
        # ======================================================================
        # 2. Non-Blocking Architecture Setup
        # ======================================================================
        # We use a thread-safe Queue to pass the AI's final dictionary decision 
        # from the background thread safely back to the main Pygame thread.
        self.ai_result_queue = queue.Queue()
        
        # A flag to prevent stacking API calls if the network is slow
        self.ai_is_thinking = False
        
        # Cooldown counter: number of frames to block new AI pings after an action is applied.
        # At 60 FPS, 45 frames = 0.75 seconds of grace period.
        self.action_cooldown = 0
        self.COOLDOWN_FRAMES = 45
        
        # Per-frame safety: distance threshold for immediate emergency dodge (pixels)
        self.CRITICAL_DISTANCE = 120
        
        # ======================================================================
        # 3. The 0.5s Trigger (2Hz) Setup
        # ======================================================================
        # Create a custom Pygame event ID for our AI radar ping
        self.AI_PING_EVENT = pygame.USEREVENT + 1
        
        # Set Pygame's internal timer to fire this event exactly every 500 milliseconds
        pygame.time.set_timer(self.AI_PING_EVENT, 500)

    def ai_worker_thread(self, current_lane: int, car_y: float):
        """
        Background worker that computes radar and calls the LLM.
        
        CRITICAL DESIGN NOTE:
        We do NOT query Qdrant here for radar data. Instead, we snapshot
        the live Pygame obstacle list directly at the time of the ping.
        This is reliable because:
        1. Qdrant's set_payload updates can lag behind 60Hz physics ticks.
        2. The live list always reflects the exact current obstacle positions.
        The Qdrant DB is still used for logging/deletion bookkeeping.
        """
        try:
            # --- Radar Computation (from live Pygame state) ---
            # Snapshot the obstacle list from the engine thread.
            # Python list reads are GIL-safe for simple attribute access.
            obstacle_snapshot = [(obs.lane, obs.y) for obs in self.engine.obstacles]
            
            # Radar window: 50px to 350px above the car's current Y
            y_near = car_y - 50
            y_far  = car_y - 350
            
            radar_hazards = [
                (lane, y) for lane, y in obstacle_snapshot
                if y_far <= y <= y_near
            ]
            
            # Format radar into a human-readable string for the LLM
            if not radar_hazards:
                radar_data = "Clear road ahead. No upcoming hazards detected."
            else:
                # Sort closest threats first (highest Y value = closest to car)
                radar_hazards.sort(key=lambda h: h[1], reverse=True)
                parts = [
                    f"Lane {lane} has a blockage {int(car_y - y)}px ahead"
                    for lane, y in radar_hazards
                ]
                radar_data = "; ".join(parts)
                print(f"[RADAR HIT] {radar_data}")
            
            # --- LLM Decision ---
            decision = get_ai_decision(
                current_lane=current_lane,
                car_y=car_y,
                radar_data_override=radar_data
            )
            
            self.ai_result_queue.put(decision)
            
        except Exception as e:
            print(f"AI Thread Error: {e}")
            self.ai_result_queue.put("STAY")

    def per_frame_safety_check(self):
        """
        60Hz Physics Safety Layer.
        Runs EVERY FRAME. Independently checks if any obstacle is within
        CRITICAL_DISTANCE of the car's current lane. If an imminent collision 
        is detected, it immediately executes a dodge WITHOUT waiting for the LLM.
        
        This decouples life-safety from LLM network latency entirely.
        """
        car = self.engine.car
        car_y = car.y
        current_lane = car.current_lane

        # Find obstacles that are critically close in the car's lane
        critical_threats = [
            obs for obs in self.engine.obstacles
            if obs.lane == current_lane and 0 < (car_y - obs.y) <= self.CRITICAL_DISTANCE
        ]

        if not critical_threats:
            return  # All clear, no intervention needed

        # Imminent collision detected — compute safe dodge direction NOW
        # Check which adjacent lanes are free of ANY nearby obstacle (within 2x critical zone)
        check_range = self.CRITICAL_DISTANCE * 2
        occupied_lanes = {
            obs.lane for obs in self.engine.obstacles
            if 0 < (car_y - obs.y) <= check_range
        }

        dodge = None
        if current_lane > 1 and (current_lane - 1) not in occupied_lanes:
            dodge = "MOVE_LEFT"
        elif current_lane < 3 and (current_lane + 1) not in occupied_lanes:
            dodge = "MOVE_RIGHT"

        if dodge:
            print(f"[60Hz SAFETY] Imminent threat in Lane {current_lane} @ "
                  f"{int(car_y - critical_threats[0].y)}px → Emergency {dodge}")
            car.execute_action(dodge)
            # Apply a short cooldown to prevent jitter on the next frame
            self.action_cooldown = self.COOLDOWN_FRAMES
            # Cancel any pending AI result since the situation has changed
            while not self.ai_result_queue.empty():
                try:
                    self.ai_result_queue.get_nowait()
                except:
                    pass
            self.ai_is_thinking = False

    def handle_events(self):
        """
        Intercepts all Pygame events. 
        Replaces `Engine.handle_events()` so we can catch our custom AI trigger.
        """
        for event in pygame.event.get():
            # 5. Graceful Shutdown
            if event.type == pygame.QUIT:
                print("\n[SHUTDOWN] Window closed. Terminating Simulation...")
                pygame.quit()
                sys.exit()
                
            # Intercept manual keyboard overrides (Useful for debugging)
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_LEFT:
                    self.engine.car.execute_action("MOVE_LEFT")
                elif event.key == pygame.K_RIGHT:
                    self.engine.car.execute_action("MOVE_RIGHT")
                    
            # The 0.5s AI Trigger Execution
            elif event.type == self.AI_PING_EVENT:
                # Block the trigger if:
                # 1. The AI is already processing a previous ping (network debounce)
                # 2. The car is still transitioning to a new lane (oscillation prevention)
                # 3. A cooldown is active after a recent action (stability grace period)
                car = self.engine.car
                car_is_settled = (car.x == car.x // 1 and abs(car.x - (100 * car.current_lane)) < 2)
                if not self.ai_is_thinking and self.action_cooldown <= 0:
                    self.ai_is_thinking = True
                    
                    # Spin up a daemon thread to perform the LangGraph network call.
                    # Daemon=True ensures threads terminate instantly if the main Pygame thread closes.
                    thread = threading.Thread(
                        target=self.ai_worker_thread,
                        args=(self.engine.car.current_lane, self.engine.car.y),
                        daemon=True
                    )
                    thread.start()

    def process_ai_results(self):
        """
        4. Execution Lifecycle Routing (Task 4.2)
        Checks every frame if the background AI thread has returned a decision.
        """
        try:
            # 1. Unpack the Agent Response
            # Non-blocking check of the queue to capture the returned response object
            response = self.ai_result_queue.get_nowait()
            
            # 4. Robust Fallbacks
            # Define our safe fallback default
            action = "STAY"
            
            try:
                # Handle extraction whether it returns a raw dict or a parsed string
                if isinstance(response, dict):
                    action = response.get("action", "STAY")
                elif isinstance(response, str):
                    action = response
                else:
                    raise ValueError(f"Unexpected response type: {type(response)}")

                # Validate the extracted action strictly
                valid_maneuvers = ["MOVE_LEFT", "MOVE_RIGHT", "STAY"]
                if action not in valid_maneuvers:
                    print(f"[AI ROUTING ANOMALY] Unrecognized string '{action}'. Defaulting to STAY.")
                    action = "STAY"
                    
            except Exception as unpack_err:
                # Catch corrupted formats or missing keys and log the anomaly
                print(f"[AI ROUTING ANOMALY] Unpacking error: {unpack_err}. Defaulting to STAY.")
                action = "STAY"
            
            print(f"[AI DECISION RECEIVED] -> Executing: {action}")
            
            # 2. Pipe Data into the Engine
            # Safely pass the validated string directly into the active Pygame car object
            self.engine.car.execute_action(action)
            
            # 3. State and Flags Reset
            # Unlock the thinking flag so the next network call can be dispatched.
            # Start a cooldown only if the car actually moved lanes (not STAY) 
            # to give it time to reach the new lane before re-evaluating.
            self.ai_is_thinking = False
            if action != "STAY":
                self.action_cooldown = self.COOLDOWN_FRAMES
                print(f"[LANE LOCK] Cooldown started ({self.COOLDOWN_FRAMES} frames). Blocking AI re-evaluation.")
            
        except queue.Empty:
            # Queue is empty, the LLM is still thinking, keep cruising at 60 FPS
            pass

    def run(self):
        """
        The Main Bridge Loop.
        Locks the visual engine to 60 FPS while transparently managing the async AI handoffs.
        """
        print("========================================")
        print("Starting RAG Racer Simulation Bridge...")
        print("Close the Pygame window to terminate.")
        print("========================================")
        
        while self.engine.running:
            # 0. Tick down the cooldown counter each frame
            if self.action_cooldown > 0:
                self.action_cooldown -= 1
                
            # 1. Event Handling Layer (UI interaction & AI triggering)
            self.handle_events()
            
            # 2. Asynchronous Handoff Layer (Read AI advisory results)
            self.process_ai_results()
            
            # 3. 60Hz Physics Safety Layer (overrides AI if needed)
            self.per_frame_safety_check()
            
            # 4. Physics & Mechanics Layer (Moving things down the screen)
            self.engine.update()
            
            # 5. Rendering Layer (Drawing the pixels)
            self.engine.draw()
            
            # Lock frame rate
            self.engine.clock.tick(FPS)
            
        print("\n[CRASH] Engine stopped internally. Bridge terminating.")
        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    bridge = SimulationBridge()
    bridge.run()
