import pygame
import random
import sys
import uuid
from database import SpatialMemoryDB

# Screen dimensions
WIDTH = 400
HEIGHT = 600
FPS = 60

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
DARK_GRAY = (50, 50, 50)
RED = (220, 50, 50)
BLUE = (50, 100, 220)

# Lane configurations
LANE_X = {
    1: 100,  # Left
    2: 200,  # Center
    3: 300   # Right
}

class Car:
    def __init__(self):
        self.current_lane = 2
        self.y = 500
        self.width = 60
        self.height = 100
        
        # Set initial x-coordinate to center of lane 2
        self.x = LANE_X[self.current_lane]

    def execute_action(self, action: str):
        """
        Takes a string action and updates the target lane accordingly.
        Clamps the lane between 1 and 3.
        """
        if action == "MOVE_LEFT":
            self.current_lane = max(1, self.current_lane - 1)
        elif action == "MOVE_RIGHT":
            self.current_lane = min(3, self.current_lane + 1)
        elif action == "STAY":
            pass  # Do nothing
            
    def update(self):
        """Smoothly transitions the car to its target lane."""
        target_x = LANE_X[self.current_lane]
        speed = 15  # Pixels per frame for lateral movement
        
        if self.x < target_x:
            self.x = min(self.x + speed, target_x)
        elif self.x > target_x:
            self.x = max(self.x - speed, target_x)

    def get_rect(self):
        return pygame.Rect(self.x - self.width // 2, self.y - self.height // 2, self.width, self.height)

    def draw(self, surface):
        # Draw main car body
        rect = pygame.Rect(self.x - self.width // 2, self.y - self.height // 2, self.width, self.height)
        pygame.draw.rect(surface, BLUE, rect, border_radius=8)
        
        # Draw a basic windshield to indicate direction
        windshield = pygame.Rect(self.x - self.width // 2 + 10, self.y - self.height // 2 + 15, self.width - 20, 25)
        pygame.draw.rect(surface, WHITE, windshield, border_radius=4)

class Obstacle:
    def __init__(self, lane):
        self.id = str(uuid.uuid4())
        self.lane = lane
        self.x = LANE_X[lane]
        self.y = -50  # Start slightly above the top boundary
        self.width = 60
        self.height = 60
        self.speed = 8  # Pixels per frame downwards

    def update(self):
        self.y += self.speed

    def get_rect(self):
        return pygame.Rect(self.x - self.width // 2, self.y - self.height // 2, self.width, self.height)

    def draw(self, surface):
        rect = pygame.Rect(self.x - self.width // 2, self.y - self.height // 2, self.width, self.height)
        pygame.draw.rect(surface, RED, rect, border_radius=5)

class BackgroundLoop:
    def __init__(self):
        self.offset = 0
        self.speed = 8  # Should match or be related to the apparent forward speed

    def update(self):
        self.offset += self.speed
        if self.offset >= 100:
            self.offset = 0

    def draw(self, surface):
        # Fill the road color
        surface.fill(DARK_GRAY)
        
        # Draw dashed lane dividers (between Lane 1 & 2, and Lane 2 & 3)
        divider_x_positions = [150, 250]
        for x_coord in divider_x_positions:
            for y in range(-100 + self.offset, HEIGHT, 100):
                pygame.draw.line(surface, WHITE, (x_coord, y), (x_coord, y + 40), 4)
        
        # Draw solid road borders (left and right edges)
        pygame.draw.line(surface, WHITE, (50, 0), (50, HEIGHT), 8)
        pygame.draw.line(surface, WHITE, (350, 0), (350, HEIGHT), 8)

class Engine:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("RAG Racer Simulation - Engine Phase 1")
        self.clock = pygame.time.Clock()
        
        self.db = SpatialMemoryDB()
        
        self.car = Car()
        self.background = BackgroundLoop()
        
        self.obstacles = []
        self.spawn_timer = 0
        self.spawn_interval = 60 # Target spawn interval in frames
        self.running = True

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.KEYDOWN:
                # Map standard arrow keys for manual testing
                if event.key == pygame.K_LEFT:
                    self.car.execute_action("MOVE_LEFT")
                elif event.key == pygame.K_RIGHT:
                    self.car.execute_action("MOVE_RIGHT")

    def update(self):
        self.background.update()
        self.car.update()
        
        # Handle obstacle spawning
        self.spawn_timer += 1
        if self.spawn_timer >= self.spawn_interval:
            lane = random.choice([1, 2, 3])
            new_obs = Obstacle(lane)
            self.obstacles.append(new_obs)
            
            # Log hazard to database
            self.db.log_hazard(lane=new_obs.lane, y_position=new_obs.y, hazard_type="blockage", hazard_id=new_obs.id)
            print(f"[DB LOG] Spawned Hazard ID={new_obs.id[:8]}... at Lane={new_obs.lane}, Y={new_obs.y}")
            
            self.spawn_timer = 0
            
            # Randomize the next spawn interval between ~0.5s to 1.5s (at 60 FPS)
            self.spawn_interval = random.randint(30, 90)
            
        # Update existing obstacles
        for obs in self.obstacles:
            obs.update()
            self.db.update_hazard_position(hazard_id=obs.id, y_position=obs.y)
            
        # Clean up obstacles that have left the screen (Memory leak prevention)
        alive_obstacles = []
        for obs in self.obstacles:
            if obs.y < HEIGHT + 100:
                alive_obstacles.append(obs)
            else:
                self.db.delete_hazard(hazard_id=obs.id)
                print(f"[DB PURGE] Removed Hazard ID={obs.id[:8]}... (Off-screen)")
        self.obstacles = alive_obstacles

        # Check for collisions
        car_rect = self.car.get_rect()
        for obs in self.obstacles:
            if car_rect.colliderect(obs.get_rect()):
                print("CRASH! Collision detected. Stopping simulation.")
                self.running = False

    def draw(self):
        # Draw background and road first
        self.background.draw(self.screen)
        
        # Draw all hazards
        for obs in self.obstacles:
            obs.draw(self.screen)
            
        # Draw player car on top
        self.car.draw(self.screen)
        
        # Flip the display buffer
        pygame.display.flip()

    def run(self):
        """Main game loop for standalone execution."""
        while self.running:
            self.handle_events()
            self.update()
            self.draw()
            self.clock.tick(FPS)

if __name__ == "__main__":
    engine = Engine()
    engine.run()
