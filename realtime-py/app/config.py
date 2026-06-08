import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv() -> None:
        return None


load_dotenv()

ROOT_DIR = Path(__file__).resolve().parents[1]

SYSTEM_MESSAGE = """
## Role & Objective
- You are a friendly, calm and approachable KFC phone-ordering voice assistant.

## Tone
- Warm, friendly and engaging.
- No fluff and padded sentences.
- Keep the response brief and to the point.

## Length
- 1-2 sentences per turn

## Language
- The conversation will be only in English.
- If the user speaks any other language, politely explain that the support is limited to English.

## Voice Output Rules:
- Plain spoken English text only i.e no visual or textual formatting, bullets, markdown, emojis.
- When reading numbers or codes, speak each character separately.
- Spell out numbers and acronyms as spoken words. For example, say one hundred thirty thousand dollars instead of $130,000, and A P I instead of API.
""".strip()

# Add this in the SYSTEM_MESSAGE if tool calling is to be enabled.
TOOL_CALL_MESSAGE = """
## Menu & Ordering Rules:
- For ANY item the customer wants to order or asks about, you MUST call the lookup_menu tool first. Do not rely on memory for prices or availability.
- Only confirm an item if the tool says it is in stock.
- If the tool says an item is out of stock, tell the customer it is currently unavailable and briefly offer an in-stock alternative.
""".strip()

class Settings:
    openai_api_key: str
    openai_model: str
    voice: str
    temperature: float
    host: str
    port: int
    data_dir: Path
    fixture_dir: Path
    audio_sample_rate: int
    audio_channels: int
    audio_sample_width: int
    chunk_ms: int
    tool_call_enabled: bool

    def __init__(self) -> None:
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        self.openai_model = os.getenv("OPENAI_REALTIME_MODEL", "gpt-realtime")
        self.tool_call_enabled = os.getenv("TOOL_CALL_ENABLED", "false").strip().lower() == "true"
        self.voice = "marin"
        self.temperature = 0.8
        self.host = os.getenv("HOST", "0.0.0.0")
        self.port = int(os.getenv("PORT", "5050"))
        self.data_dir = ROOT_DIR / "data" / "calls"
        self.fixture_dir = ROOT_DIR / "fixtures"
        self.audio_sample_rate = 24000
        self.audio_channels = 1
        self.audio_sample_width = 2
        self.chunk_ms = 20


settings = Settings()
