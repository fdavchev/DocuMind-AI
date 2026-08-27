# config.py

# Model Settings
TEMPERATURE = 0.7            # 0.0 = focused/deterministic, 1.0 = creative/random
MAX_TOKENS = 512             # Maximum length of each response

# App Settings
APP_TITLE = "Local AI Chatbot"
APP_ICON = "🤖"
USER_AVATAR = "🧑"
ASSISTANT_AVATAR = "🤖"

AVAILABLE_MODELS = [
    "llama3",
    "mistral",
    "phi3",
    "llava"
]

DEFAULT_MODEL = "llava"

MODEL_NAME = DEFAULT_MODEL    # Change DEFAULT_MODEL above to switch models

# System Prompt — edit this to give your assistant a personality
SYSTEM_PROMPT = """You are a helpful, friendly, local vision-language AI assistant. 
You can analyze both text and images accurately and concisely. 
Be direct, avoid fluff, 
and clearly state if you cannot see an image or don't know an answer."""