"""
Environment Guard — Prevents accidental mainnet/testnet misconfigurations.

This module enforces strict environment separation at agent startup, making it 
IMPOSSIBLE to accidentally run the mainnet agent against testnet contracts or vice versa.
All production operations require the MAINNET_CONFIRMATION_TOKEN environment variable, 
which is never committed to Git and never in .env.example.
"""

import os
import sys
from typing import Literal


class EnvironmentMismatchError(Exception):
    """Raised when the deployment environment does not match the expected environment."""
    
    def __init__(self, expected: str, actual: str):
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"Environment mismatch: expected '{expected}' but deployment_environment is '{actual}'. "
            f"This is a critical safety check to prevent mainnet/testnet confusion. "
            f"Verify your .env DEPLOYMENT_ENVIRONMENT setting and retry."
        )


class MissingConfirmationTokenError(Exception):
    """Raised when MAINNET_CONFIRMATION_TOKEN is required but missing."""
    
    def __init__(self):
        super().__init__(
            "MAINNET_CONFIRMATION_TOKEN environment variable is required for mainnet operations. "
            "This token is never committed to Git and must be set only on the production server "
            "as an out-of-band configuration step. If you are deploying to mainnet, set this token "
            "in your production environment and retry."
        )


class EnvironmentGuard:
    """
    Guard that enforces strict environment separation and mainnet confirmation requirements.
    
    This class must be instantiated and assert_environment() called as the absolute first 
    operation in both testnet validation scripts and the mainnet startup script.
    """
    
    def __init__(self):
        """Initialize the environment guard."""
        self.current_environment = os.getenv("DEPLOYMENT_ENVIRONMENT", "").lower().strip()
    
    def assert_environment(self, expected: Literal["testnet", "mainnet", "local"]) -> None:
        """
        Assert that the current deployment environment matches the expected value.
        
        For mainnet operations, also require MAINNET_CONFIRMATION_TOKEN.
        
        Args:
            expected: The expected deployment environment ("testnet", "mainnet", or "local").
            
        Raises:
            EnvironmentMismatchError: If the current environment does not match expected.
            MissingConfirmationTokenError: If mainnet is expected but confirmation token is missing.
        """
        expected_lower = expected.lower().strip()
        
        # Verify environment matches
        if self.current_environment != expected_lower:
            raise EnvironmentMismatchError(expected_lower, self.current_environment)
        
        # For mainnet, require the confirmation token
        if expected_lower == "mainnet":
            confirmation_token = os.getenv("MAINNET_CONFIRMATION_TOKEN", "").strip()
            if not confirmation_token or len(confirmation_token) < 32:
                raise MissingConfirmationTokenError()
    
    def is_mainnet(self) -> bool:
        """Check if the current environment is mainnet."""
        return self.current_environment == "mainnet"
    
    def is_testnet(self) -> bool:
        """Check if the current environment is testnet."""
        return self.current_environment == "testnet"
    
    def is_local(self) -> bool:
        """Check if the current environment is local."""
        return self.current_environment == "local"


# Global guard instance for module-level access
_guard = None


def get_guard() -> EnvironmentGuard:
    """Get or create the global environment guard instance."""
    global _guard
    if _guard is None:
        _guard = EnvironmentGuard()
    return _guard


if __name__ == "__main__":
    """
    Command-line interface for environment verification.
    Usage: python -m agent.configs.environment_guard --expect mainnet
    """
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Verify deployment environment matches expected value."
    )
    parser.add_argument(
        "--expect",
        choices=["testnet", "mainnet", "local"],
        required=True,
        help="Expected deployment environment",
    )
    
    args = parser.parse_args()
    
    try:
        guard = get_guard()
        guard.assert_environment(args.expect)
        print(f"✓ Environment check passed: {args.expect}", file=sys.stderr)
        sys.exit(0)
    except (EnvironmentMismatchError, MissingConfirmationTokenError) as e:
        print(f"✗ Environment check failed: {e}", file=sys.stderr)
        sys.exit(1)
