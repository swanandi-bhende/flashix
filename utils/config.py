from typing import List, Optional
import os
from pydantic import BaseSettings, Field, ValidationError


class Settings(BaseSettings):
    # 0G Chain (use env names like 0G_RPC_ENDPOINT)
    OG_RPC_ENDPOINT: str = Field(..., env="0G_RPC_ENDPOINT")
    OG_CHAIN_ID: int = Field(..., env="0G_CHAIN_ID")
    DEPLOYER_PRIVATE_KEY: Optional[str] = Field(None, env="DEPLOYER_PRIVATE_KEY")

    # TEE
    TEE_ENDPOINT: str = Field(..., env="TEE_ENDPOINT")
    TEE_API_KEY: str = Field(..., env="TEE_API_KEY")

    # Mempool
    MEMPOOL_PROVIDER: str = Field(..., env="MEMPOOL_PROVIDER")
    MEMPOOL_API_KEY: Optional[str] = Field(None, env="MEMPOOL_API_KEY")

    # Gemini
    GEMINI_API_KEY: Optional[str] = Field(None, env="GEMINI_API_KEY")

    # Arbitrage
    MIN_PROFIT_MARGIN_PERCENT: float = Field(1.0, env="MIN_PROFIT_MARGIN_PERCENT")

    class Config:
        env_file = ".env"
        case_sensitive = False


def validate_env():
    try:
        settings = Settings()
    except ValidationError as e:
        print("Error: missing or invalid environment variables:\n", e)
        raise SystemExit(1)
    return settings


if __name__ == "__main__":
    s = validate_env()
    print("Environment validated.")
    print(s.dict())
