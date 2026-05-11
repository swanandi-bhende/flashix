"""
Main Flashix agent executor.
Assembles all components (LLM, tools, memory, prompt) into a running AgentExecutor.
Entry point for signal processing and autonomous arbitrage decision-making.
"""

import os
import sys
from typing import Dict, List, Any, Optional

# Import components (these will be available once dependencies are installed)
try:
    from langchain.agents import AgentExecutor, create_react_agent
    from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
    from langchain_google_genai import ChatGoogleGenerativeAI
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    print("Warning: LangChain packages not yet installed. Full agent functionality will be available once dependencies are installed.")

from agent_config import AgentConfig, ConfigurationError
from agent_memory import FlashixMemory
from prompts.system_prompt import SYSTEM_PROMPT
from tools import (
    ValidateInferenceSignal,
    AssessMarketConditions,
    QueryTradeHistory,
    LogExecutionDecision,
)
from reasoning import ChainOfThoughtExecutor, MarketStressCalculator, TraceDB


class FlashixAgent:
    """
    Main Flashix arbitrage agent.
    Orchestrates signal validation, market assessment, historical analysis,
    decision logging, and autonomous execution authorization.
    """
    
    def __init__(self, config: Optional[AgentConfig] = None):
        """
        Initialize the Flashix agent.
        
        Args:
            config: AgentConfig instance. If None, loads from environment.
        
        Raises:
            ConfigurationError: If configuration is invalid
        """
        # Load configuration
        if config is None:
            self.config = AgentConfig.load_from_env()
        else:
            self.config = config
        
        # Initialize memory
        self.memory = FlashixMemory(memory_window_k=self.config.memory_window_k)
        self.memory.seed_with_trade_history("opportunities.db")
        
        # Initialize tools
        self.tools = [
            ValidateInferenceSignal(),
            AssessMarketConditions(),
            QueryTradeHistory(),
            LogExecutionDecision(),
        ]

        # Initialize structured reasoning components
        self.market_stress_calculator = MarketStressCalculator()
        self.reasoning_executor = ChainOfThoughtExecutor(
            model_name=self.config.gemini_model,
            temperature=self.config.gemini_temperature,
            max_output_tokens=self.config.gemini_max_tokens,
            dry_run_mode=self.config.dry_run_mode,
        )
        self.trace_db = TraceDB()
        
        # Initialize LLM and agent executor
        self.agent_executor: Optional[AgentExecutor] = None
        self._initialize_executor()
    
    def _initialize_executor(self) -> None:
        """
        Initialize the LangChain AgentExecutor with all components.
        
        Wires together:
        1. LLM (ChatGoogleGenerativeAI)
        2. Tools (our custom tools)
        3. Prompt (system prompt + message placeholders)
        4. Memory (ConversationBufferMemory)
        5. Agent executor with safety constraints
        """
        if not LANGCHAIN_AVAILABLE:
            print("ERROR: LangChain not installed. Cannot initialize agent executor.")
            return
        
        try:
            # Initialize LLM with Gemini configuration
            llm = ChatGoogleGenerativeAI(
                model=self.config.gemini_model,
                temperature=self.config.gemini_temperature,
                max_output_tokens=self.config.gemini_max_tokens,
                convert_system_message_to_human=True,  # Gemini doesn't support system role natively
            )
            
            # Build prompt template with system prompt + message history
            prompt = ChatPromptTemplate.from_messages([
                ("system", SYSTEM_PROMPT),
                MessagesPlaceholder("chat_history"),
                ("human", "{input}"),
                MessagesPlaceholder("agent_scratchpad"),
            ])
            
            # Create the ReAct agent
            agent = create_react_agent(llm, self.tools, prompt)
            
            # Wrap in AgentExecutor with safety constraints
            self.agent_executor = AgentExecutor(
                agent=agent,
                tools=self.tools,
                memory=None,  # Using custom FlashixMemory instead
                max_iterations=self.config.max_iterations,
                max_execution_time=self.config.max_execution_time_seconds,
                early_stopping_method="generate",
                handle_parsing_errors=True,
                verbose=self.config.verbose,
            )
            
            if self.config.verbose:
                print("✓ Flashix Agent initialized successfully")
                print(f"  - Model: {self.config.gemini_model}")
                print(f"  - Temperature: {self.config.gemini_temperature}")
                print(f"  - Max iterations: {self.config.max_iterations}")
                print(f"  - Execution timeout: {self.config.max_execution_time_seconds}s")
                print(f"  - Dry run mode: {self.config.dry_run_mode}")
        
        except Exception as e:
            print(f"ERROR: Failed to initialize agent executor: {e}")
            raise
    
    def set_verbose(self, verbose: bool) -> None:
        """
        Set verbose output mode.
        
        Args:
            verbose: True to print reasoning steps, False for silent operation
        """
        self.config.verbose = verbose
        if self.agent_executor:
            self.agent_executor.verbose = verbose
    
    def invoke(self, signal_input: str) -> Dict[str, Any]:
        """
        Invoke the agent with a signal input.
        
        Args:
            signal_input: Formatted signal string from SignalProcessor
        
        Returns:
            Agent response dictionary with decision and reasoning
        """
        if not self.agent_executor:
            return {
                "error": "Agent executor not initialized. Check configuration and dependencies.",
                "decision": "REJECT"
            }
        
        try:
            # Add input to memory
            self.memory.add_human_message(signal_input)
            
            # Invoke agent with input
            result = self.agent_executor.invoke({"input": signal_input})
            
            # Add output to memory
            if "output" in result:
                self.memory.add_ai_message(result["output"])
            
            return result
        
        except Exception as e:
            error_msg = f"Agent invocation failed: {e}"
            print(f"ERROR: {error_msg}")
            
            return {
                "error": error_msg,
                "decision": "REJECT",
                "reasoning": "Agent execution failed; rejecting signal as precaution"
            }

    def process_signal(self, signal: Any) -> Any:
        """Process a structured inference signal through the reasoning pipeline."""
        from signal_processor import SignalProcessor

        processor = SignalProcessor(self)
        return processor.process(signal)
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get summary statistics from agent memory."""
        return self.memory.get_summary_stats()
    
    def save_memory(self, filepath: str = "data/agent_memory.json") -> None:
        """Persist memory to file."""
        self.memory.persist(filepath)
        if self.config.verbose:
            print(f"✓ Memory persisted to {filepath}")
    
    def load_memory(self, filepath: str = "data/agent_memory.json") -> bool:
        """Restore memory from file."""
        success = self.memory.restore(filepath)
        if success and self.config.verbose:
            print(f"✓ Memory restored from {filepath}")
        return success


def initialize_agent(
    config: Optional[AgentConfig] = None,
    verbose: bool = True
) -> FlashixAgent:
    """
    Initialize and return a Flashix agent.
    
    Args:
        config: Optional AgentConfig. If None, loads from environment.
        verbose: Whether to print initialization messages
    
    Returns:
        Initialized FlashixAgent instance
    
    Raises:
        ConfigurationError: If configuration is invalid
    """
    if config is None:
        config = AgentConfig.load_from_env()
    
    config.verbose = verbose
    
    return FlashixAgent(config)


if __name__ == "__main__":
    # Development initialization test
    print("Initializing Flashix Agent...")
    
    try:
        agent = initialize_agent(verbose=True)
        print("\nAgent initialized successfully!")
        print(f"Memory stats: {agent.get_memory_stats()}")
    
    except ConfigurationError as e:
        print(f"Configuration error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Initialization failed: {e}")
        sys.exit(1)
