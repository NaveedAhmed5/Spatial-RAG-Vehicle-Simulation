import uuid
from qdrant_client import QdrantClient
from qdrant_client.http import models

class SpatialMemoryDB:
    def __init__(self):
        """
        Initializes an in-memory Qdrant client for spatial RAG lookups.
        Creates the 'hazards' collection if it doesn't already exist.
        """
        try:
            # Connect to an in-memory Qdrant instance
            self.client = QdrantClient(":memory:")
            self.collection_name = "hazards"
            
            # Check if collection exists
            if not self.client.collection_exists(self.collection_name):
                # Create a minimal vector profile since we only care about payload filtering.
                # A dimension size of 1 satisfies the schema requirement.
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=models.VectorParams(
                        size=1, 
                        distance=models.Distance.COSINE
                    )
                )
                print(f"Collection '{self.collection_name}' initialized.")
        except Exception as e:
            print(f"Error initializing Qdrant client: {e}")

    def log_hazard(self, lane: int, y_position: float, hazard_type: str, hazard_id: str):
        """
        Upserts a hazard point into the 'hazards' collection.
        Stores the spatial and descriptive attributes inside the payload.
        """
        try:
            point = models.PointStruct(
                id=hazard_id,
                vector=[0.0],  # Dummy vector: we filter by payload, not semantic distance
                payload={
                    "lane": lane,
                    "y_position": y_position,
                    "hazard_type": hazard_type
                }
            )
            self.client.upsert(
                collection_name=self.collection_name,
                points=[point]
            )
        except Exception as e:
            print(f"Error logging hazard {hazard_id}: {e}")

    def update_hazard_position(self, hazard_id: str, y_position: float):
        """
        Updates the Y position payload of an existing hazard.
        Essential for tracking moving obstacles in real-time.
        """
        try:
            self.client.set_payload(
                collection_name=self.collection_name,
                payload={"y_position": y_position},
                points=[hazard_id]
            )
        except Exception as e:
            print(f"Error updating hazard {hazard_id}: {e}")

    def delete_hazard(self, hazard_id: str):
        """
        Deletes a hazard from the database (e.g., when it leaves the screen).
        """
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.PointIdsList(
                    points=[hazard_id]
                )
            )
        except Exception as e:
            print(f"Error deleting hazard {hazard_id}: {e}")

    def get_upcoming_hazards(self, car_current_y: float) -> list:
        """
        Radar array lookup: Retrieves hazards located 200 to 400 pixels *ahead* of the car.
        Because Y=0 is the top of the screen and obstacles fall downwards towards the car,
        'ahead' means smaller Y values.
        """
        # radar_closest: 40px behind/next-to car (so we don't merge into passing obstacles)
        # radar_furthest: 600px ahead (entire screen)
        y_max = car_current_y + 40   # Closest boundary
        y_min = car_current_y - 600  # Furthest boundary
        
        try:
            # Query Qdrant with payload filtering
            records, _ = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="y_position",
                            range=models.Range(
                                gte=y_min,
                                lte=y_max
                            )
                        )
                    ]
                ),
                limit=100,  # Grab all matches in the radar block
                with_payload=True
            )
            
            # Extract payloads and sort them so the closest threats (largest Y) appear first
            hazards = [record.payload for record in records]
            hazards.sort(key=lambda h: h["y_position"], reverse=True)
            return hazards
            
        except Exception as e:
            print(f"Error fetching upcoming hazards: {e}")
            return []


# ==============================================================================
# INTEGRATION HOOKS & INSTRUCTIONS FOR `src/engine.py`
# ==============================================================================
# 
# 1. Import and Initialize Database:
#    from database import SpatialMemoryDB
#    import uuid
#    
#    # Inside Engine.__init__():
#    self.db = SpatialMemoryDB()
#
# 2. Assign Unique IDs and Log Spawns:
#    # Inside Engine.update() when spawning an obstacle:
#    hazard_id = str(uuid.uuid4())
#    new_obstacle = Obstacle(lane)
#    new_obstacle.id = hazard_id  # Attach the ID to the obstacle object
#    self.obstacles.append(new_obstacle)
#    
#    # Log it immediately to Qdrant
#    self.db.log_hazard(lane=lane, y_position=new_obstacle.y, hazard_type="block", hazard_id=hazard_id)
#
# 3. Update Database Positions on Tick:
#    # Inside Engine.update() when applying gravity to obstacles:
#    for obs in self.obstacles:
#        obs.update()
#        self.db.update_hazard_position(hazard_id=obs.id, y_position=obs.y)
#
# 4. Clean Up Memory when Obstacles go off-screen:
#    # Instead of just filtering out the obstacles, explicitly delete from DB:
#    alive_obstacles = []
#    for obs in self.obstacles:
#        if obs.y < HEIGHT + 100:
#            alive_obstacles.append(obs)
#        else:
#            self.db.delete_hazard(hazard_id=obs.id)
#    self.obstacles = alive_obstacles
#
# 5. Radar Query (For the Agent loop later):
#    # This reads the database context for prompt generation
#    upcoming = self.db.get_upcoming_hazards(car_current_y=self.car.y)
# ==============================================================================

if __name__ == "__main__":
    # Quick standalone test of the Spatial Memory Database
    print("Testing Spatial Memory DB...")
    db = SpatialMemoryDB()
    
    # Mock some data
    hid1 = str(uuid.uuid4())
    hid2 = str(uuid.uuid4())
    hid3 = str(uuid.uuid4())
    
    # Log hazards
    db.log_hazard(lane=2, y_position=150, hazard_type="block", hazard_id=hid1)
    db.log_hazard(lane=3, y_position=250, hazard_type="block", hazard_id=hid2)
    db.log_hazard(lane=1, y_position=450, hazard_type="block", hazard_id=hid3) # Too close to car
    
    # Simulate a radar ping from a car at Y=500
    # Radar window: Y=100 to Y=300
    print("\nSimulating Car Radar Ping at Y=500...")
    radar_blips = db.get_upcoming_hazards(500)
    for h in radar_blips:
        print(f"Radar Contact: {h}")
        
    # Clean up test
    db.delete_hazard(hid1)
    db.delete_hazard(hid2)
    db.delete_hazard(hid3)
    print("\nDatabase cleared successfully.")
