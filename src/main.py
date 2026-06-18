import pygame
import sys
import threading
import queue

# 1. Component Imports
# Import our standalone physical game engine and its frame rate
from engine import Engine, FPS
# Import the LangGraph routing manager
from manager import get_ai_decision, calculate_safe_maneuver

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
        
        # 3. Hybrid Strategy
        self.current_policy = {"strategy": "CAUTIOUS", "preferred_lane": 2}
        
        # A flag to prevent stacking API calls if the network is slow
        self.ai_is_thinking = False
        
        # Cooldown counter: number of frames to block new AI pings after an action is applied.
        # At 60 FPS, 45 frames = 0.75 seconds of grace period.
        self.action_cooldown = 0
        self.COOLDOWN_FRAMES = 45
        
        # Per-frame safety: distance threshold for immediate emergency dodge (pixels)
        self.CRITICAL_DISTANCE = 120
        
        # ======================================================================
        # The 2s Trigger (0.5Hz) Setup
        # ======================================================================
        # Create a custom Pygame event ID for our AI radar ping
        self.AI_PING_EVENT = pygame.USEREVENT + 1
        
        pygame.time.set_timer(self.AI_PING_EVENT, 2000)

    def ai_worker_thread(self, current_lane: int, car_y: float):
        """
        Background thread that fetches the new Strategy from the LLM.
        """
        try:
            # We pass the engine's populated Qdrant memory database into the LangGraph function
            policy = get_ai_decision(
                current_lane=current_lane, 
                car_y=car_y, 
                db_override=self.engine.db
            )
            self.ai_result_queue.put(policy)
        except Exception as e:
            print(f"AI Thread Error: {e}")
            self.ai_result_queue.put({"strategy": "CAUTIOUS", "preferred_lane": 2})

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.engine.running = False
                
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_LEFT:
                    self.engine.car.execute_action("MOVE_LEFT")
                elif event.key == pygame.K_RIGHT:
                    self.engine.car.execute_action("MOVE_RIGHT")
                    
            elif event.type == self.AI_PING_EVENT:
                if not self.ai_is_thinking:
                    self.ai_is_thinking = True
                    self.engine.ai_thinking = True  # Update HUD badge
                    
                    thread = threading.Thread(
                        target=self.ai_worker_thread,
                        args=(self.engine.car.current_lane, self.engine.car.y),
                        daemon=True
                    )
                    thread.start()

    def process_ai_results(self):
        try:
            response = self.ai_result_queue.get_nowait()
            
            if isinstance(response, dict) and "strategy" in response:
                self.current_policy = response
                print(f"[STRATEGY UPDATED] -> {self.current_policy}")
            
            self.ai_is_thinking = False
            self.engine.ai_thinking = False  # Reset HUD badge
            
        except queue.Empty:
            pass

    def run(self):
        print("========================================")
        print("Starting RAG Racer Simulation Bridge (Hybrid Architecture)...")
        print("Close the Pygame window to terminate.")
        print("========================================")
        
        while self.engine.running:
            # 0. Process Pathfinding and Cooldown
            if self.action_cooldown > 0:
                self.action_cooldown -= 1
            else:
                # Synchronous Python Reflex Engine
                maneuver = calculate_safe_maneuver(
                    current_lane=self.engine.car.current_lane,
                    obstacles=self.engine.obstacles,
                    car_y=self.engine.car.y,
                    policy=self.current_policy
                )
                
                action = maneuver.get("action", "STAY")
                if action != "STAY":
                    print(f"[REFLEX DODGE] -> {action} (Strategy: {self.current_policy.get('strategy')})")
                    self.engine.car.execute_action(action)
                    self.action_cooldown = self.COOLDOWN_FRAMES
                    print(f"[LANE LOCK] Cooldown started ({self.COOLDOWN_FRAMES} frames).")
                
            # 1. Event Handling Layer
            self.handle_events()
            
            # 2. Asynchronous Handoff Layer
            self.process_ai_results()
            
            # 3. Physics & Mechanics Layer
            self.engine.update()
            self.engine.draw()
            self.engine.clock.tick(FPS)
            
        print("\n[CRASH] Engine stopped internally. Bridge terminating.")
        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    bridge = SimulationBridge()
    bridge.run()
