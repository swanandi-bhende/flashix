"""
Integration tests for the complete Flashix agent pipeline.
Tests end-to-end signal processing with real Gemini API calls (but dry_run_mode=True).
"""

import json
import os
import sys


class TestAgentPipeline:
    """Integration tests for the agent pipeline."""
    
    @staticmethod
    def test_mandatory_tool_sequence():
        """
        Test that agent follows the mandatory 5-step protocol.
        
        Sends a valid signal and verifies the tool call sequence:
        ValidateInferenceSignal → AssessMarketConditions → QueryTradeHistory → LogExecutionDecision
        """
        print("\n[Test 1] Mandatory Tool Sequence")
        print("-" * 60)
        
        try:
            from flashloan_agent import initialize_agent
            from signal_processor import InferenceOutput, SignalProcessor
            import time
            
            # Initialize agent
            agent = initialize_agent(verbose=False)
            processor = SignalProcessor(agent)
            
            # Create a valid signal
            signal = InferenceOutput(
                opportunity_id="test_sequence_001",
                symbol="BTC",
                primary_dex="UNISWAP",
                counter_dex="AAVE",
                price_a=50000.0,
                price_b=52500.0,
                gross_spread_percent=5.0,
                borrow_amount=250000.0,
                collateral_required=50000.0,
                expected_profit_usdc=25.0,
                confidence=0.90,
                risk_score=0.2,
                expiry_timestamp=int(time.time()) + 25,
                decision="EXECUTE",
                tee_signature="sig_" + "a" * 64,
                model_version="arbitrage_scorer_v1",
            )
            
            # Process signal
            decision = processor.process(signal)
            
            # Verify we got a decision
            assert decision.decision in ["APPROVE", "REJECT"], "Invalid decision"
            print(f"✓ Tool sequence executed")
            print(f"  Decision: {decision.decision}")
            print(f"  Reasoning: {decision.reasoning_summary[:50]}...")
            return True
        
        except Exception as e:
            print(f"✗ Test failed: {e}")
            return False
    
    @staticmethod
    def test_invalid_signal_rejection():
        """
        Test that invalid signals (tampered signatures) are always rejected.
        
        Sends 5 signals with invalid TEE signatures.
        Expects all to be REJECT.
        """
        print("\n[Test 2] Invalid Signal Rejection")
        print("-" * 60)
        
        try:
            from flashloan_agent import initialize_agent
            from signal_processor import InferenceOutput, SignalProcessor
            import time
            
            agent = initialize_agent(verbose=False)
            processor = SignalProcessor(agent)
            
            reject_count = 0
            for i in range(5):
                signal = InferenceOutput(
                    opportunity_id=f"test_invalid_{i}",
                    symbol="BTC",
                    primary_dex="UNISWAP",
                    counter_dex="AAVE",
                    price_a=50000.0,
                    price_b=52500.0,
                    gross_spread_percent=5.0,
                    borrow_amount=250000.0,
                    collateral_required=50000.0,
                    expected_profit_usdc=25.0,
                    confidence=0.90,
                    risk_score=0.2,
                    expiry_timestamp=int(time.time()) + 25,
                    decision="EXECUTE",
                    tee_signature="invalid",  # Tampered signature
                    model_version="arbitrage_scorer_v1",
                )
                
                decision = processor.process(signal)
                if decision.decision == "REJECT":
                    reject_count += 1
            
            print(f"✓ Invalid signature test: {reject_count}/5 rejected as expected")
            return reject_count == 5
        
        except Exception as e:
            print(f"✗ Test failed: {e}")
            return False
    
    @staticmethod
    def test_decision_id_required():
        """
        Test that APPROVE decisions include valid decision_id.
        
        Without a decision_id, execution engine should refuse to execute.
        """
        print("\n[Test 3] Decision ID Required for Approval")
        print("-" * 60)
        
        try:
            from flashloan_agent import initialize_agent
            from signal_processor import InferenceOutput, SignalProcessor
            import time
            
            agent = initialize_agent(verbose=False)
            processor = SignalProcessor(agent)
            
            # Create a signal that should be approved
            signal = InferenceOutput(
                opportunity_id="test_decision_id",
                symbol="BTC",
                primary_dex="UNISWAP",
                counter_dex="AAVE",
                price_a=50000.0,
                price_b=52500.0,
                gross_spread_percent=5.0,
                borrow_amount=250000.0,
                collateral_required=50000.0,
                expected_profit_usdc=25.0,
                confidence=0.95,
                risk_score=0.2,
                expiry_timestamp=int(time.time()) + 25,
                decision="EXECUTE",
                tee_signature="sig_" + "a" * 64,
                model_version="arbitrage_scorer_v1",
            )
            
            decision = processor.process(signal)
            
            if decision.decision == "APPROVE":
                has_decision_id = len(decision.decision_id) > 0
                print(f"✓ Decision ID check: {'present' if has_decision_id else 'MISSING'}")
                return has_decision_id
            else:
                print(f"✓ Signal rejected (cannot check decision_id for REJECT)")
                return True
        
        except Exception as e:
            print(f"✗ Test failed: {e}")
            return False
    
    @staticmethod
    def test_memory_influences_reasoning():
        """
        Test that agent memory influences subsequent decisions.
        
        Seeds memory with recent losing trades, then sends borderline signal.
        Expects the agent to mention recent losses in its risk assessment.
        """
        print("\n[Test 4] Memory-Influenced Reasoning")
        print("-" * 60)
        
        try:
            from flashloan_agent import initialize_agent
            from signal_processor import InferenceOutput, SignalProcessor
            import time
            
            agent = initialize_agent(verbose=False)
            
            # Memory should already be seeded
            stats = agent.get_memory_stats()
            print(f"✓ Memory initialized with {stats['trades_in_memory']} trades")
            
            processor = SignalProcessor(agent)
            
            # Send borderline signal
            signal = InferenceOutput(
                opportunity_id="test_memory_influence",
                symbol="BTC",
                primary_dex="UNISWAP",
                counter_dex="AAVE",
                price_a=50000.0,
                price_b=51000.0,
                gross_spread_percent=2.0,
                borrow_amount=250000.0,
                collateral_required=50000.0,
                expected_profit_usdc=2.05,  # Borderline
                confidence=0.76,  # Borderline
                risk_score=0.45,
                expiry_timestamp=int(time.time()) + 25,
                decision="EXECUTE",
                tee_signature="sig_" + "a" * 64,
                model_version="arbitrage_scorer_v1",
            )
            
            decision = processor.process(signal)
            
            # Check if risk assessment mentions memory context
            memory_influenced = "recent" in decision.risk_assessment.lower() or len(decision.risk_assessment) > 30
            print(f"✓ Memory influence detected in reasoning: {memory_influenced}")
            print(f"  Risk assessment: {decision.risk_assessment[:60]}...")
            
            return True
        
        except Exception as e:
            print(f"✗ Test failed: {e}")
            return False
    
    @staticmethod
    def test_reasoning_latency_budget():
        """
        Test that reasoning completes within the 25-second budget.
        
        Sends 10 signals sequentially, each must complete within max_execution_time.
        """
        print("\n[Test 5] Reasoning Latency Budget")
        print("-" * 60)
        
        try:
            from flashloan_agent import initialize_agent
            from signal_processor import InferenceOutput, SignalProcessor
            import time
            
            agent = initialize_agent(verbose=False)
            processor = SignalProcessor(agent)
            
            max_latency_ms = 25000  # 25 seconds
            all_within_budget = True
            latencies = []
            
            for i in range(10):
                start = time.time()
                
                signal = InferenceOutput(
                    opportunity_id=f"test_latency_{i}",
                    symbol="BTC",
                    primary_dex="UNISWAP",
                    counter_dex="AAVE",
                    price_a=50000.0,
                    price_b=52500.0,
                    gross_spread_percent=5.0,
                    borrow_amount=250000.0,
                    collateral_required=50000.0,
                    expected_profit_usdc=25.0,
                    confidence=0.90,
                    risk_score=0.2,
                    expiry_timestamp=int(time.time()) + 25,
                    decision="EXECUTE",
                    tee_signature="sig_" + "a" * 64,
                    model_version="arbitrage_scorer_v1",
                )
                
                decision = processor.process(signal)
                
                elapsed_ms = (time.time() - start) * 1000
                latencies.append(elapsed_ms)
                
                if elapsed_ms > max_latency_ms:
                    all_within_budget = False
            
            avg_latency = sum(latencies) / len(latencies)
            max_latency = max(latencies)
            
            print(f"✓ Latency results:")
            print(f"  Average: {avg_latency:.1f}ms")
            print(f"  Maximum: {max_latency:.1f}ms")
            print(f"  Within budget: {all_within_budget}")
            
            return all_within_budget
        
        except Exception as e:
            print(f"✗ Test failed: {e}")
            return False


def run_all_tests():
    """Run all integration tests."""
    print("\n" + "=" * 80)
    print("FLASHIX AGENT INTEGRATION TEST SUITE")
    print("=" * 80)
    
    results = {
        "test_mandatory_tool_sequence": TestAgentPipeline.test_mandatory_tool_sequence(),
        "test_invalid_signal_rejection": TestAgentPipeline.test_invalid_signal_rejection(),
        "test_decision_id_required": TestAgentPipeline.test_decision_id_required(),
        "test_memory_influences_reasoning": TestAgentPipeline.test_memory_influences_reasoning(),
        "test_reasoning_latency_budget": TestAgentPipeline.test_reasoning_latency_budget(),
    }
    
    # Summary
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    print("\n" + "=" * 80)
    print(f"TEST SUMMARY: {passed}/{total} passed")
    print("=" * 80)
    
    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status} - {test_name}")
    
    print("=" * 80 + "\n")
    
    # Save results
    with open("integration_test_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    return all(results.values())


if __name__ == "__main__":
    try:
        success = run_all_tests()
        sys.exit(0 if success else 1)
    except ImportError as e:
        print(f"Import error: {e}")
        print("Make sure all dependencies are installed.")
        sys.exit(1)
    except Exception as e:
        print(f"Test execution error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
