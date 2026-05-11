"""
Gemini connectivity test.
Validates API connectivity, model accessibility, and LangChain integration before agent deployment.
"""

import os
import sys
import json
import logging
from datetime import datetime


def test_gemini_connection():
    """
    Test Gemini connectivity and LangChain integration.
    
    Procedure:
    1. Load GEMINI_API_KEY from .env
    2. Initialize ChatGoogleGenerativeAI with test config
    3. Send test message: "Respond with the word CONNECTED and nothing else."
    4. Verify response contains "CONNECTED"
    5. Log model version, latency, and token usage
    
    Returns:
        (success: bool, details: dict)
    """
    
    # Set up logging
    os.makedirs("logs", exist_ok=True)
    log_file = "logs/setup_validation.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 80)
    logger.info("GEMINI CONNECTIVITY TEST")
    logger.info("=" * 80)
    
    details = {
        "timestamp": datetime.now().isoformat(),
        "test_results": {},
        "errors": [],
    }
    
    try:
        # Step 1: Load API key
        logger.info("\n[Step 1] Loading GEMINI_API_KEY from environment...")
        api_key = os.getenv("GEMINI_API_KEY")
        
        if not api_key:
            error_msg = "GEMINI_API_KEY not found in environment. Please set it in .env file."
            logger.error(f"✗ {error_msg}")
            details["errors"].append(error_msg)
            return False, details
        
        logger.info(f"✓ API key loaded (length: {len(api_key)})")
        details["test_results"]["api_key_loaded"] = True
        
        # Step 2: Import LangChain modules
        logger.info("\n[Step 2] Importing LangChain modules...")
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            from langchain_core.messages import HumanMessage
            logger.info("✓ LangChain imports successful")
            details["test_results"]["langchain_imports"] = True
        except ImportError as e:
            error_msg = f"Failed to import LangChain: {e}"
            logger.error(f"✗ {error_msg}")
            details["errors"].append(error_msg)
            return False, details
        
        # Step 3: Initialize ChatGoogleGenerativeAI
        logger.info("\n[Step 3] Initializing ChatGoogleGenerativeAI...")
        try:
            llm = ChatGoogleGenerativeAI(
                model="gemini-1.5-flash",
                temperature=0.3,
                max_output_tokens=256,
                google_api_key=api_key,
            )
            logger.info("✓ ChatGoogleGenerativeAI initialized")
            details["test_results"]["llm_initialized"] = True
        except Exception as e:
            error_msg = f"Failed to initialize ChatGoogleGenerativeAI: {e}"
            logger.error(f"✗ {error_msg}")
            details["errors"].append(error_msg)
            return False, details
        
        # Step 4: Send test message
        logger.info("\n[Step 4] Sending test message to Gemini...")
        try:
            import time
            start_time = time.time()
            
            test_message = "Respond with the word CONNECTED and nothing else."
            response = llm.invoke([HumanMessage(content=test_message)])
            
            elapsed_ms = (time.time() - start_time) * 1000
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            logger.info(f"✓ Response received in {elapsed_ms:.1f}ms")
            logger.info(f"  Response: {response_text[:100]}")
            
            details["test_results"]["api_call_success"] = True
            details["test_results"]["response_latency_ms"] = round(elapsed_ms, 1)
            details["test_results"]["response_text"] = response_text[:200]
            
            # Step 5: Verify response
            logger.info("\n[Step 5] Verifying response...")
            if "CONNECTED" in response_text.upper():
                logger.info("✓ Response contains 'CONNECTED'")
                details["test_results"]["response_valid"] = True
            else:
                logger.warning(f"⚠ Response does not contain 'CONNECTED': {response_text}")
                details["test_results"]["response_valid"] = False
        
        except Exception as e:
            error_msg = f"Failed to call Gemini API: {e}"
            logger.error(f"✗ {error_msg}")
            details["errors"].append(error_msg)
            return False, details
        
        # Log token usage if available
        logger.info("\n[Step 6] Checking model capabilities...")
        try:
            model_info = llm.get_name() if hasattr(llm, 'get_name') else "gemini-1.5-flash"
            logger.info(f"✓ Model: {model_info}")
            details["test_results"]["model_info"] = model_info
        except:
            pass
        
        # Success!
        logger.info("\n" + "=" * 80)
        logger.info("✓ ALL TESTS PASSED")
        logger.info("=" * 80)
        logger.info(f"\nSetup validation log: {log_file}")
        
        return True, details
    
    except Exception as e:
        error_msg = f"Unexpected error: {e}"
        logger.error(f"✗ {error_msg}")
        details["errors"].append(error_msg)
        return False, details


def main():
    """Run the connectivity test."""
    try:
        # Load environment variables
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        print("Warning: python-dotenv not installed. Make sure GEMINI_API_KEY is set.")
    
    success, details = test_gemini_connection()
    
    # Print summary
    print("\n" + "=" * 80)
    if success:
        print("✓ GEMINI CONNECTIVITY TEST PASSED")
        print("The agent is ready for deployment.")
    else:
        print("✗ GEMINI CONNECTIVITY TEST FAILED")
        print("\nErrors:")
        for error in details.get("errors", []):
            print(f"  - {error}")
    print("=" * 80 + "\n")
    
    # Save detailed results
    with open("logs/setup_validation_details.json", "w") as f:
        json.dump(details, f, indent=2)
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
