import os

# pydantic-ai otherwise prints a promotional banner on its first run.
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")
