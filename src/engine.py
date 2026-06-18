import pygame
import random
import sys
import uuid
from database import SpatialMemoryDB

# === SCREEN CONFIG ===
WIDTH  = 400
HEIGHT = 600
FPS    = 60

# === ROAD GEOMETRY ===
ROAD_LEFT  = 50
ROAD_RIGHT = 350

# === LANE CONFIG ===
LANE_X = {1: 100, 2: 200, 3: 300}

# === COLOR PALETTE ===
C_SKY        = (10,  12,  22)
C_GRASS_L    = (12,  32,  12)
C_ROAD       = (28,  30,  40)
C_ROAD_ALT   = (33,  35,  46)
C_EDGE       = (220, 220, 220)
C_DASH       = (190, 190, 190)
C_SPEEDLINE  = (40,  42,  56)

C_CAR_BODY   = (35,  100, 250)
C_CAR_ROOF   = (18,  58,  175)
C_CAR_GLASS  = (130, 195, 255)
C_HEADLIGHT  = (255, 255, 210)
C_TAILLIGHT  = (255, 35,  35)
C_WHEEL      = (18,  18,  28)
C_CAR_SHINE  = (80,  155, 255)

C_OBS_BODY   = (185, 42,  22)
C_OBS_STRIPE = (235, 165, 0)
C_OBS_GLOW   = (255, 75,  40)
C_OBS_DARK   = (120, 25,  10)

C_WHITE      = (255, 255, 255)
C_CYAN       = (70,  200, 255)
C_GREEN      = (70,  235, 115)
C_YELLOW     = (255, 215, 40)
C_RED_HUD    = (255, 60,  60)
C_DIM        = (55,  58,  75)


class Particle:
    """Velocity streak particle for speed effect."""
    def __init__(self):
        self.reset(initial=True)

    def reset(self, initial=False):
        self.x      = random.randint(ROAD_LEFT + 5, ROAD_RIGHT - 5)
        self.y      = random.uniform(-20, HEIGHT if initial else 0)
        self.speed  = random.uniform(7, 14)
        self.length = random.randint(10, 28)
        self.alpha  = random.randint(25, 100)

    def update(self):
        self.y += self.speed
        if self.y > HEIGHT + 30:
            self.reset()

    def draw(self, surface):
        if self.alpha <= 0:
            return
        s = pygame.Surface((2, self.length), pygame.SRCALPHA)
        s.fill((255, 255, 255, self.alpha))
        surface.blit(s, (self.x, int(self.y)))


class BackgroundLoop:
    def __init__(self):
        self.offset    = 0.0
        self.speed     = 3
        self.particles = [Particle() for _ in range(30)]

    def update(self):
        self.offset = (self.offset + self.speed) % 80
        for p in self.particles:
            p.update()

    def draw(self, surface):
        # Fill entire background
        surface.fill(C_SKY)

        # Off-road left & right (grass / kerb)
        pygame.draw.rect(surface, C_GRASS_L, (0, 0, ROAD_LEFT, HEIGHT))
        pygame.draw.rect(surface, C_GRASS_L, (ROAD_RIGHT, 0, WIDTH - ROAD_RIGHT, HEIGHT))

        # Kerb stripes (red-white alternating on edges)
        kerb_h = 40
        for i in range(HEIGHT // kerb_h + 2):
            y = int(i * kerb_h + self.offset * 0.8) % (HEIGHT + kerb_h) - kerb_h
            col = (180, 30, 30) if i % 2 == 0 else (200, 200, 200)
            pygame.draw.rect(surface, col, (ROAD_LEFT - 8, y, 8, kerb_h))
            pygame.draw.rect(surface, col, (ROAD_RIGHT, y, 8, kerb_h))

        # Road surface
        pygame.draw.rect(surface, C_ROAD, (ROAD_LEFT, 0, ROAD_RIGHT - ROAD_LEFT, HEIGHT))

        # Road texture: faint horizontal bands scrolling downward
        for i in range(0, HEIGHT + 100, 80):
            y = int((i + self.offset * 1.6) % (HEIGHT + 70)) - 35
            pygame.draw.line(surface, C_SPEEDLINE, (ROAD_LEFT, y), (ROAD_RIGHT, y), 1)

        # Speed particles
        for p in self.particles:
            p.draw(surface)

        # Lane dividers (dashed white between lanes)
        for div_x in (150, 250):
            for y in range(-70 + int(self.offset), HEIGHT, 70):
                pygame.draw.rect(surface, C_DASH, (div_x - 2, y, 4, 42), border_radius=1)

        # Road edge solid lines
        pygame.draw.rect(surface, C_EDGE, (ROAD_LEFT - 5, 0, 5, HEIGHT))
        pygame.draw.rect(surface, C_EDGE, (ROAD_RIGHT, 0, 5, HEIGHT))


class Car:
    def __init__(self):
        self.current_lane = 2
        self.y     = 490
        self.width = 52
        self.height= 86
        self.x     = float(LANE_X[self.current_lane])

    def execute_action(self, action: str):
        if action == "MOVE_LEFT":
            self.current_lane = max(1, self.current_lane - 1)
        elif action == "MOVE_RIGHT":
            self.current_lane = min(3, self.current_lane + 1)

    def update(self):
        target = float(LANE_X[self.current_lane])
        spd = 13
        if self.x < target:
            self.x = min(self.x + spd, target)
        elif self.x > target:
            self.x = max(self.x - spd, target)

    def get_rect(self):
        return pygame.Rect(int(self.x) - self.width // 2,
                           self.y - self.height // 2,
                           self.width, self.height)

    def draw(self, surface):
        cx, cy, w, h = int(self.x), self.y, self.width, self.height

        # Wheels (drawn behind body)
        ww, wh = 10, 16
        for wx, wy in [
            (cx - w//2 - 4, cy - h//4),
            (cx + w//2 - 6, cy - h//4),
            (cx - w//2 - 4, cy + h//4 - wh//2),
            (cx + w//2 - 6, cy + h//4 - wh//2),
        ]:
            pygame.draw.rect(surface, C_WHEEL, (wx, wy, ww, wh), border_radius=3)

        # Main body
        body = pygame.Rect(cx - w//2, cy - h//2, w, h)
        pygame.draw.rect(surface, C_CAR_BODY, body, border_radius=11)

        # Roof (darker shade)
        roof = pygame.Rect(cx - w//2 + 8, cy - h//2 + 17, w - 16, h // 2 - 8)
        pygame.draw.rect(surface, C_CAR_ROOF, roof, border_radius=7)

        # Front windshield
        ws = pygame.Rect(cx - w//2 + 10, cy - h//2 + 19, w - 20, 17)
        pygame.draw.rect(surface, C_CAR_GLASS, ws, border_radius=4)

        # Rear window
        rw = pygame.Rect(cx - w//2 + 10, cy - h//2 + h//2 - 5, w - 20, 14)
        pygame.draw.rect(surface, C_CAR_GLASS, rw, border_radius=4)

        # Headlights (top/front)
        for lx in [cx - w//2 + 3, cx + w//2 - 11]:
            pygame.draw.rect(surface, C_HEADLIGHT, (lx, cy - h//2 + 4, 8, 5), border_radius=2)
            # Glow dot
            pygame.draw.circle(surface, (255, 255, 240), (lx + 4, cy - h//2 + 6), 2)

        # Taillights (bottom/rear)
        for lx in [cx - w//2 + 3, cx + w//2 - 11]:
            pygame.draw.rect(surface, C_TAILLIGHT, (lx, cy + h//2 - 9, 8, 5), border_radius=2)

        # Body side highlight streak
        pygame.draw.line(surface, C_CAR_SHINE,
                         (cx - w//2 + 5, cy - h//2 + 13),
                         (cx - w//2 + 5, cy + h//2 - 13), 2)


class Obstacle:
    def __init__(self, lane):
        self.id     = str(uuid.uuid4())
        self.lane   = lane
        self.x      = float(LANE_X[lane])
        self.y      = float(-55)
        self.width  = 52
        self.height = 58
        self.speed  = 3.0

    def update(self):
        self.y += self.speed

    def get_rect(self):
        return pygame.Rect(int(self.x) - self.width  // 2,
                           int(self.y) - self.height // 2,
                           self.width, self.height)

    def draw(self, surface):
        cx, cy, w, h = int(self.x), int(self.y), self.width, self.height

        # Main body
        body = pygame.Rect(cx - w//2, cy - h//2, w, h)
        pygame.draw.rect(surface, C_OBS_BODY, body, border_radius=7)

        # Warning diagonal stripes (clipped to body)
        stripe_surf = pygame.Surface((w, h), pygame.SRCALPHA)
        for i in range(-h, w + h, 16):
            pts = [(i, 0), (i + 9, 0), (i + 9 + h, h), (i + h, h)]
            pygame.draw.polygon(stripe_surf, (*C_OBS_STRIPE, 90), pts)
        surface.blit(stripe_surf, (cx - w//2, cy - h//2))

        # Dark bottom panel
        pygame.draw.rect(surface, C_OBS_DARK,
                         (cx - w//2 + 2, cy + h//2 - 14, w - 4, 12), border_radius=4)

        # Outline
        pygame.draw.rect(surface, C_OBS_STRIPE, body, 2, border_radius=7)

        # Warning lights (flashing red, top corners)
        for lx in [cx - w//2 + 3, cx + w//2 - 11]:
            pygame.draw.rect(surface, C_OBS_GLOW, (lx, cy - h//2 + 4, 8, 5), border_radius=2)

        # Exclamation mark symbol
        pygame.draw.rect(surface, C_OBS_STRIPE, (cx - 3, cy - h//4 + 2, 6, h//2 - 10), border_radius=2)
        pygame.draw.circle(surface, C_OBS_STRIPE, (cx, cy + h//4 - 2), 3)


class HUD:
    def __init__(self):
        pygame.font.init()
        self.font_lg = pygame.font.SysFont("Consolas", 17, bold=True)
        self.font_sm = pygame.font.SysFont("Consolas", 13)
        self.score   = 0

    def update(self):
        self.score += 1

    def draw(self, surface, car_lane: int, ai_thinking: bool):
        # --- TOP BAR ---
        top_h = 46
        top_bg = pygame.Surface((WIDTH, top_h), pygame.SRCALPHA)
        top_bg.fill((5, 6, 14, 210))
        surface.blit(top_bg, (0, 0))
        pygame.draw.line(surface, C_CYAN, (0, top_h), (WIDTH, top_h), 1)

        # Distance (left)
        dist_m = self.score // 10
        dist_surf = self.font_lg.render(f"DIST  {dist_m:>5}m", True, C_CYAN)
        surface.blit(dist_surf, (10, 13))

        # AI badge (right)
        if ai_thinking:
            ai_txt   = "AI ..."
            ai_color = C_YELLOW
        else:
            ai_txt   = "AI RDY"
            ai_color = C_GREEN
        ai_surf = self.font_sm.render(ai_txt, True, ai_color)
        surface.blit(ai_surf, (WIDTH - ai_surf.get_width() - 10, 15))

        # --- BOTTOM BAR ---
        bot_h   = 40
        bot_top = HEIGHT - bot_h
        bot_bg  = pygame.Surface((WIDTH, bot_h), pygame.SRCALPHA)
        bot_bg.fill((5, 6, 14, 200))
        surface.blit(bot_bg, (0, bot_top))
        pygame.draw.line(surface, C_CYAN, (0, bot_top), (WIDTH, bot_top), 1)

        lane_label = {1: "◀ LEFT", 2: "● CENTER", 3: "RIGHT ▶"}
        lbl_surf = self.font_sm.render(f"LANE:  {lane_label[car_lane]}", True, C_WHITE)
        surface.blit(lbl_surf, (WIDTH // 2 - lbl_surf.get_width() // 2, bot_top + 12))

        # Lane dots
        for ln, lx in LANE_X.items():
            is_active = (ln == car_lane)
            col    = C_CYAN if is_active else C_DIM
            radius = 6 if is_active else 4
            pygame.draw.circle(surface, col, (lx, bot_top + 6), radius)
            if is_active:
                pygame.draw.circle(surface, C_WHITE, (lx, bot_top + 6), radius, 1)


class Engine:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("RAG Racer — Spatial AI Simulation")
        self.clock  = pygame.time.Clock()

        self.db         = SpatialMemoryDB()
        self.car        = Car()
        self.background = BackgroundLoop()
        self.hud        = HUD()

        self.obstacles     = []
        self.spawn_timer   = 0
        self.spawn_interval= 90
        self.running       = True

        # Exposed to bridge so it can update the HUD AI badge
        self.ai_thinking   = False

    # ------------------------------------------------------------------
    # Constants for safe spawning
    # ------------------------------------------------------------------
    SPAWN_Y        = -55.0
    MIN_VERT_GAP   = 200   # px — minimum vertical separation between any two obstacles
    MAX_OBSTACLES  = 3     # Up to 3 obstacles on screen; 240px gap keeps them spaced safely

    # ------------------------------------------------------------------
    # Smart spawning: guarantees at least one escape lane is always free
    # ------------------------------------------------------------------
    def _get_safe_spawn_lane(self) -> int | None:
        """
        Returns a lane to spawn in, or None to skip this spawn cycle.

        Rules enforced:
          1. Never more than MAX_OBSTACLES obstacles on screen.
          2. New obstacle must be at least MIN_VERT_GAP pixels below any
             existing obstacle's current Y (enforces the >100px side-by-side gap).
          3. If 2 lanes are already occupied in the approach zone, only
             the remaining free lane is eligible (escape-lane guarantee).
        """
        # Rule 1 — cap concurrent obstacles
        if len(self.obstacles) >= self.MAX_OBSTACLES:
            return None

        # Rule 2 — minimum vertical gap from spawn point
        # Since all obstacles share the same speed, a gap at spawn time
        # is preserved for the entire lifespan of both obstacles.
        for obs in self.obstacles:
            if (obs.y - self.SPAWN_Y) < self.MIN_VERT_GAP:  # obs.y < 105
                return None  # Previous obstacle still too close to spawn zone

        # Rule 3 — escape lane guarantee
        car_y = self.car.y
        active_lanes = {obs.lane for obs in self.obstacles if obs.y < car_y - 30}

        if len(active_lanes) >= 2:
            free = [l for l in [1, 2, 3] if l not in active_lanes]
            return random.choice(free) if free else None

        # Default: pick randomly, avoid the same lane as a recently spawned obstacle
        fresh = {obs.lane for obs in self.obstacles if obs.y < 100}
        candidates = [l for l in [1, 2, 3] if l not in fresh] or [1, 2, 3]
        return random.choice(candidates)

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_LEFT:
                    self.car.execute_action("MOVE_LEFT")
                elif event.key == pygame.K_RIGHT:
                    self.car.execute_action("MOVE_RIGHT")

    def update(self):
        self.background.update()
        self.car.update()
        self.hud.update()

        # Spawn logic
        self.spawn_timer += 1
        if self.spawn_timer >= self.spawn_interval:
            lane = self._get_safe_spawn_lane()
            if lane is not None:
                obs = Obstacle(lane)
                self.obstacles.append(obs)
                self.db.log_hazard(lane=obs.lane, y_position=obs.y,
                                   hazard_type="blockage", hazard_id=obs.id)
                print(f"[DB LOG] Spawned Hazard ID={obs.id[:8]}... at Lane={obs.lane}, Y={int(obs.y)}")

            self.spawn_timer   = 0
            self.spawn_interval = random.randint(50, 90)   # ~0.8 – 1.5 s

        # Move obstacles & sync DB
        for obs in self.obstacles:
            obs.update()
            self.db.update_hazard_position(hazard_id=obs.id, y_position=obs.y)

        # Purge off-screen obstacles
        alive = []
        for obs in self.obstacles:
            if obs.y < HEIGHT + 100:
                alive.append(obs)
            else:
                self.db.delete_hazard(hazard_id=obs.id)
                print(f"[DB PURGE] Removed Hazard ID={obs.id[:8]}... (Off-screen)")
        self.obstacles = alive

        # Collision detection
        car_rect = self.car.get_rect()
        for obs in self.obstacles:
            if car_rect.colliderect(obs.get_rect()):
                print("CRASH! Collision detected. Stopping simulation.")
                self.running = False

    def draw(self):
        self.background.draw(self.screen)
        for obs in self.obstacles:
            obs.draw(self.screen)
        self.car.draw(self.screen)
        self.hud.draw(self.screen, self.car.current_lane, self.ai_thinking)
        pygame.display.flip()

    def run(self):
        """Standalone execution loop."""
        while self.running:
            self.handle_events()
            self.update()
            self.draw()
            self.clock.tick(FPS)


if __name__ == "__main__":
    engine = Engine()
    engine.run()
