import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "backend" / "data"
HISTORY_FILE = DATA_DIR / "run_history.json"
PROMPT_GLOB = "[[]System Prompt[]]*.txt"
SAMPLE_PATTERN = "*.json"
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4")
ALLOWED_ORIGIN = os.getenv("ALLOWED_ORIGIN", "http://localhost:5173")

MODEL_PRICING_PER_1M_TOKENS: dict[str, dict[str, float]] = {
    "gpt-5.4": {"input": 2.50, "cached_input": 0.25, "output": 15.00},
    "gpt-5": {"input": 1.25, "cached_input": 0.125, "output": 10.00},
    "gpt-5-mini": {"input": 0.25, "cached_input": 0.025, "output": 2.00},
    "gpt-5-nano": {"input": 0.05, "cached_input": 0.005, "output": 0.40},
    "gpt-5-codex": {"input": 1.25, "cached_input": 0.125, "output": 10.00},
    "gpt-5.1-codex": {"input": 1.25, "cached_input": 0.125, "output": 10.00},
    "gpt-5.1-codex-mini": {"input": 0.25, "cached_input": 0.025, "output": 2.00},
}

MODEL_DESCRIPTIONS = {
    "gpt-5.4": "고품질 모델 - 소개글/세계관 생성용",
    "gpt-5": "중간 성능 모델",
    "gpt-5-mini": "경량 모델 - 데이터 수집/교차 검증용",
    "gpt-5-nano": "초경량 모델 - 비용 최소화용",
    "gpt-5-codex": "코드 생성 특화 모델",
    "gpt-5.1-codex": "고급 코드 생성 모델",
    "gpt-5.1-codex-mini": "경량 코드 생성 모델",
}
