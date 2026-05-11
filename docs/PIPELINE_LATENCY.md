# Pipeline Latency Baseline

This file will contain p95 latency results for each pipeline stage after running integration tests.

Target p95s:
- mempool→inference_request: < 50ms
- inference_request→inference_complete: < 1500ms
- inference_complete→agent_decision: < 25000ms
- agent_decision→execution_confirmed: < 15000ms
- execution_confirmed→settlement: < 500ms

Run `pytest tests/integration/test_full_pipeline.py -v` to populate.
