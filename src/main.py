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
        
        # ======================================================================
        # 3. The 0.5s Trigger (2Hz) Setup
        # ======================================================================
        # Create a custom Pygame event ID for our AI radar ping
        self.AI_PING_EVENT = pygame.USEREVENT + 1
        
        # Set Pygame's internal timer to fire this event exactly every 500 milliseconds
        pygame.time.set_timer(self.AI_PING_EVENT, 500)

    def ai_worker_thread(self, current_lane: int, car_y: float):
        """
        Background worker that talks to Groq via LangGraph.
        Running this OFF the main thread prevents the 60 FPS UI from freezing 
        during the 200ms-500ms network latency window.
        """
        try:
            # Dispatch the LangGraph routing.
            # CRITICAL: We pass the engine's active database instance (db_override)
            # into the graph so the AI radar reads the exact same spatial memory 
            # the Pygame loop is currently populating!
            decision = get_ai_decision(
                current_lane=current_lane, 
                car_y=car_y, 
                db_override=self.engine.db
            )
            
            # Put the resulting string action cleanly into the queue
            self.ai_result_queue.put(decision)
            
        except Exception as e:
            print(f"AI Thread Error: {e}")
            # If the network fails or times out, default to a safe maneuver to avoid crashes
            self.ai_result_queue.put("STAY")

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
                # If the AI is already processing a previous ping, ignore this one to prevent stacking
                if not self.ai_is_thinking:
                    self.ai_is_thinking = True
                    # print("[2Hz TICK] Dispatching background AI request...")
                    
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
        4. Execution Handoff
        Checks every frame if the background AI thread has returned a decision.
        """
        try:
            # Non-blocking check of the queue
            action = self.ai_result_queue.get_nowait()
            
            print(f"[AI DECISION RECEIVED] -> Executing: {action}")
            
            # Pass the AI's string action directly into the car's steering mechanism
            self.engine.car.execute_action(action)
            
            # Reset flag so the next 500ms trigger can fire
            self.ai_is_thinking = False
            
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
            # 1. Event Handling Layer (UI interaction & AI triggering)
            self.handle_events()
            
            # 2. Asynchronous Handoff Layer (Read AI results)
            self.process_ai_results()
            
            # 3. Physics & Mechanics Layer (Moving things down the screen)
            self.engine.update()
            
            # 4. Rendering Layer (Drawing the pixels)
            self.engine.draw()
            
            # Lock frame rate
            self.engine.clock.tick(FPS)
            
        print("\n[CRASH] Engine stopped internally. Bridge terminating.")
        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    bridge = SimulationBridge()
    bridge.run()
