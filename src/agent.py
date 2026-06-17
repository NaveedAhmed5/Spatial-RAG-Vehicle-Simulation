import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq

def initialize_llm() -> ChatGroq:
    """
    Initializes the Groq LLM client.
    Ensures environment variables are loaded and the model is configured 
    for low latency (llama-3.1-8b-instant) and deterministic behavior (temperature=0).
    """
    # 1. Environment Variable Loading
    # Calculate the path dynamically so it works regardless of where the script is executed from
    # while adhering to the requirement of reaching back to the root directory's .env file
    dotenv_path = os.path.join(os.path.dirname(__file__), "../.env")
    load_dotenv(dotenv_path=dotenv_path)

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY is missing. Please ensure your .env file is present in the root directory and contains the key.")

    # 2. Groq LLM Initialization
    llm = ChatGroq(
        model="llama-3.1-8b-instant",
        temperature=0,
        groq_api_key=api_key
    )
    
    return llm

if __name__ == "__main__":
    print("--- Groq Client Sanity Check ---")
    try:
        # Initialize the LLM
        agent_llm = initialize_llm()
        
        # 3. Sanity Check Block
        print("API Key loaded successfully. Pinging Groq cloud infrastructure...")
        
        # Test completion call requesting a specific word to verify deterministic behavior
        response = agent_llm.invoke("Are you receiving this? Please respond with exactly the word: 'Ready'")
        
        print(f"\n[Response]: {response.content}")
        print("✅ System Check Passed: LLM agent connected to Groq successfully.")
        
    except ValueError as ve:
        # Catch errors related to missing .env file or missing GROQ_API_KEY
        print(f"\n❌ Configuration Error: {ve}")
    except Exception as e:
        # Catch connection errors or API rejection issues
        print(f"\n❌ Network/API Error: Could not connect to Groq infrastructure.\nDetails: {e}")
