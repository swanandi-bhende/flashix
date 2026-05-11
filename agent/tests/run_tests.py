"""
Test suite for the Flashix agent.
Runs 50+ mock signals through the agent and validates reasoning consistency.
"""

import json
import sys
import time
from typing import Dict, List, Any


def test_agent_with_mock_signals(agent: Any, signals: List[Any]) -> Dict[str, Any]:
    """
    Test the agent with a set of mock signals.
    
    Args:
        agent: Initialized FlashixAgent instance
        signals: List of InferenceOutput signals
    
    Returns:
        Test results dictionary
    """
    from signal_processor import SignalProcessor
    
    processor = SignalProcessor(agent)
    test_results = {
        "total_signals": len(signals),
        "passed": 0,
        "failed": 0,
        "errors": [],
        "decisions": [],
        "latencies": [],
    }
    
    for i, signal in enumerate(signals):
        try:
            start_time = time.time()
            decision = processor.process(signal)
            elapsed_ms = (time.time() - start_time) * 1000
            
            test_results["latencies"].append(elapsed_ms)
            test_results["decisions"].append({
                "opportunity_id": signal.opportunity_id,
                "decision": decision.decision,
                "reasoning": decision.reasoning_summary[:50] + "...",
                "elapsed_ms": round(elapsed_ms, 1),
            })
            
            test_results["passed"] += 1
        
        except Exception as e:
            test_results["failed"] += 1
            test_results["errors"].append({
                "opportunity_id": signal.opportunity_id,
                "error": str(e),
            })
    
    return test_results


def validate_clear_approve_signals(results: Dict[str, Any]) -> bool:
    """
    Validate that clear approve signals were approved.
    
    Returns:
        True if all clear approve signals got APPROVE decision
    """
    clear_approves = [
        d for d in results["decisions"]
        if "clear_approve" in d["opportunity_id"]
    ]
    return all(d["decision"] == "APPROVE" for d in clear_approves)


def validate_reject_signals(results: Dict[str, Any]) -> bool:
    """
    Validate that all reject scenarios were rejected.
    
    Returns:
        True if all reject signals got REJECT decision
    """
    rejects = [
        d for d in results["decisions"]
        if any(x in d["opportunity_id"] for x in [
            "low_profit", "low_conf", "invalid_sig"
        ])
    ]
    return all(d["decision"] == "REJECT" for d in rejects)


def validate_consistency(results: Dict[str, Any]) -> bool:
    """
    Validate that identical scenarios get consistent decisions.
    
    Returns:
        True if consistency score is high
    """
    # Group by scenario type
    scenarios = {}
    for decision in results["decisions"]:
        # Extract scenario from opportunity_id
        scenario_type = "_".join(decision["opportunity_id"].split("_")[:-1])
        if scenario_type not in scenarios:
            scenarios[scenario_type] = []
        scenarios[scenario_type].append(decision["decision"])
    
    # Check consistency
    consistent = 0
    for scenario_type, decisions_list in scenarios.items():
        if len(set(decisions_list)) == 1:  # All same decision
            consistent += 1
    
    consistency_pct = (consistent / len(scenarios) * 100) if scenarios else 0
    return consistency_pct > 90.0  # Allow 90% consistency


def print_test_results(results: Dict[str, Any]) -> None:
    """Print test results in human-readable format."""
    print("\n" + "=" * 80)
    print("FLASHIX AGENT TEST RESULTS")
    print("=" * 80)
    print(f"Total signals tested: {results['total_signals']}")
    print(f"Passed: {results['passed']}")
    print(f"Failed: {results['failed']}")
    
    if results["latencies"]:
        avg_latency = sum(results["latencies"]) / len(results["latencies"])
        print(f"Average reasoning latency: {avg_latency:.1f}ms")
    
    print("\nDecision breakdown:")
    approve_count = sum(1 for d in results["decisions"] if d["decision"] == "APPROVE")
    reject_count = sum(1 for d in results["decisions"] if d["decision"] == "REJECT")
    print(f"  - APPROVE: {approve_count}")
    print(f"  - REJECT: {reject_count}")
    
    print("\nSample decisions:")
    for decision in results["decisions"][:5]:
        print(f"  - {decision['opportunity_id']}: {decision['decision']} ({decision['elapsed_ms']}ms)")
    
    if results["errors"]:
        print(f"\nErrors ({len(results['errors'])}):")
        for error in results["errors"][:3]:
            print(f"  - {error['opportunity_id']}: {error['error']}")
    
    print("=" * 80 + "\n")


if __name__ == "__main__":
    print("Testing Flashix Agent with 40+ mock signals...")
    print("Note: This requires LangChain and Google Gemini API to be configured.")
    
    try:
        from flashloan_agent import initialize_agent
        from mock_signal_generator import MockSignalGenerator
        
        # Initialize agent
        print("\n1. Initializing agent...")
        agent = initialize_agent(verbose=False)
        print("✓ Agent initialized")
        
        # Generate test signals
        print("\n2. Generating test signals...")
        generator = MockSignalGenerator()
        signals = generator.generate_all_test_signals()
        print(f"✓ Generated {len(signals)} test signals")
        
        # Run tests
        print("\n3. Running agent tests...")
        results = test_agent_with_mock_signals(agent, signals)
        
        # Print results
        print_test_results(results)
        
        # Validate expectations
        print("4. Validating test results...")
        clear_approve_ok = validate_clear_approve_signals(results)
        print(f"  ✓ Clear approve validation: {'PASS' if clear_approve_ok else 'FAIL'}")
        
        reject_ok = validate_reject_signals(results)
        print(f"  ✓ Reject signal validation: {'PASS' if reject_ok else 'FAIL'}")
        
        consistency_ok = validate_consistency(results)
        print(f"  ✓ Consistency validation: {'PASS' if consistency_ok else 'FAIL'}")
        
        # Save results
        print("\n5. Saving test results...")
        with open("test_results.json", "w") as f:
            json.dump(results, f, indent=2)
        print("✓ Results saved to test_results.json")
        
        # Summary
        all_pass = clear_approve_ok and reject_ok and consistency_ok and results["failed"] == 0
        print("\n" + ("="*80))
        print(f"OVERALL TEST RESULT: {'✓ PASS' if all_pass else '✗ FAIL'}")
        print("="*80 + "\n")
        
        sys.exit(0 if all_pass else 1)
    
    except ImportError as e:
        print(f"\nImport error: {e}")
        print("Make sure all dependencies are installed and you're in the agent directory.")
        sys.exit(1)
    except Exception as e:
        print(f"\nTest execution error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
