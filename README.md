# 🏎️ RAG Racer Simulation

🌟 **Highlights**
* 🧠 **Hybrid AI Architecture**: Combines a 60 FPS deterministic Python Reflex Engine for split-second dodges with a LangGraph LLM for high-level strategic planning.
* 🗺️ **Spatial RAG Integration**: Uses Qdrant vector database to store and retrieve spatial hazard data in real-time.
* ⚡ **Token-Efficient**: The LLM evaluates playstyles (e.g., AGGRESSIVE vs CAUTIOUS) every 5 seconds, rather than per frame, saving massive API costs and bypassing rate limits.
* 📊 **A/B Testing Framework**: Built-in deterministic testing suite to benchmark the Python Reflex Engine against the LLM Strategic Commander.
* 🎨 **Neon Synthwave Aesthetic**: A beautiful, glowing Pygame environment.

ℹ️ **Overview**
RAG Racer is an autonomous driving simulation that explores how Large Language Models (LLMs) can be integrated into high-speed, real-time control systems. Traditional approaches that force an LLM to dictate every granular steering input often fail due to network latency and rate limits. 

RAG Racer solves this by introducing a **Hybrid Architecture**. The car's physical survival is managed by a native, zero-latency Python Reflex Engine that calculates perfect slides and gap dodges at 60 frames per second. Meanwhile, an asynchronous LangGraph agent acts as the "Strategic Commander," polling a Qdrant database of road hazards every 5 seconds to dictate the car's overarching playstyle and lane preferences.

This project demonstrates how AI and deterministic logic can be safely decoupled in real-time applications, making it highly relevant for researchers and developers experimenting with LLM-driven robotics and game AI.

🚀 **Usage instructions**
To start the live simulation and watch the Hybrid Architecture in action:

```bash
# Run the main Pygame simulation loop
python src/main.py
```

To run the scientific A/B comparison test (runs identical deterministic obstacle patterns with and without the LLM active):

```bash
# Run the A/B benchmarking tool
python src/comparison_test.py
```

⬇️ **Installation instructions**
This project requires Python 3.11+ and an active Groq API key for the LLM pipeline.

1. Clone the repository and navigate to the project directory.
2. Install the required dependencies:
   ```bash
   pip install -r src/requirements.txt
   ```
3. Create a `.env` file in the root directory and add your Groq API key:
   ```env
   GROQ_API_KEY=your_api_key_here
   ```

✍️ **Author**
Created by Naveed Ahmed as a Summer Project to explore the boundaries of Spatial RAG and real-time LLM integration.

💭 **Invite feedback and contribute**
If you found this architecture interesting or have suggestions on how to improve the LangGraph prompts to prevent the car from making overly aggressive lane choices, please feel free to open an Issue or start a Discussion! 

Contributions to the Pygame engine, UI enhancements, or new AI strategies are always welcome. Check out the source code and feel free to submit a Pull Request!
