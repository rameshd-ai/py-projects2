"""
Base Agent Class
All specialized agents inherit from this base class
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime
import asyncio
import structlog

from src.config import settings


class AgentError(Exception):
    """Base exception for agent errors"""
    pass


class AgentTimeoutError(AgentError):
    """Raised when agent execution times out"""
    pass


class BaseAgent(ABC):
    """
    Base class for all AI agents
    
    All agents must implement:
    - execute() method
    - name property
    - description property
    """
    
    def __init__(
        self,
        timeout: Optional[int] = None,
        retry_count: int = 3,
        **kwargs
    ):
        """
        Initialize base agent
        
        Args:
            timeout: Execution timeout in seconds
            retry_count: Number of retries on failure
            **kwargs: Additional agent-specific parameters
        """
        self.timeout = timeout or settings.agent_timeout
        self.retry_count = retry_count
        self.logger = structlog.get_logger(self.__class__.__name__)
        
        # Execution tracking
        self._execution_count = 0
        self._success_count = 0
        self._failure_count = 0
        self._total_execution_time = 0.0
        
        # Store any additional kwargs
        self.config = kwargs
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Agent name"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Agent description"""
        pass
    
    @abstractmethod
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute agent's main task
        
        Args:
            input_data: Input data dictionary
            
        Returns:
            Output data dictionary
            
        Raises:
            AgentError: If execution fails
        """
        pass
    
    async def run(
        self,
        input_data: Dict[str, Any],
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        Run agent with timeout, retry logic, and tracking
        
        Args:
            input_data: Input data
            progress_callback: Optional callback for progress updates
            
        Returns:
            Agent output data
            
        Raises:
            AgentError: If execution fails after retries
            AgentTimeoutError: If execution times out
        """
        start_time = datetime.now()
        self._execution_count += 1
        
        # Log start
        self.logger.info(
            "agent_started",
            agent=self.name,
            execution_count=self._execution_count
        )
        
        # Progress callback
        if progress_callback:
            await progress_callback(self.name, "started", 0)
        
        # Retry loop
        last_error = None
        for attempt in range(1, self.retry_count + 1):
            try:
                # Execute with timeout
                result = await asyncio.wait_for(
                    self.execute(input_data),
                    timeout=self.timeout
                )
                
                # Success!
                execution_time = (datetime.now() - start_time).total_seconds()
                self._success_count += 1
                self._total_execution_time += execution_time
                
                self.logger.info(
                    "agent_completed",
                    agent=self.name,
                    duration=execution_time,
                    attempt=attempt
                )
                
                if progress_callback:
                    await progress_callback(self.name, "completed", 100)
                
                # Add metadata to result
                result["_agent_metadata"] = {
                    "agent_name": self.name,
                    "execution_time": execution_time,
                    "attempt": attempt,
                    "timestamp": start_time.isoformat()
                }
                
                return result
                
            except asyncio.TimeoutError as e:
                last_error = AgentTimeoutError(
                    f"Agent {self.name} timed out after {self.timeout}s"
                )
                self.logger.error(
                    "agent_timeout",
                    agent=self.name,
                    attempt=attempt,
                    timeout=self.timeout
                )
                
            except AgentError as e:
                last_error = e
                self.logger.error(
                    "agent_error",
                    agent=self.name,
                    attempt=attempt,
                    error=str(e)
                )
                
            except Exception as e:
                last_error = AgentError(f"Agent {self.name} failed: {str(e)}")
                self.logger.error(
                    "agent_unexpected_error",
                    agent=self.name,
                    attempt=attempt,
                    error=str(e),
                    error_type=type(e).__name__
                )
            
            # Wait before retry (exponential backoff)
            if attempt < self.retry_count:
                wait_time = 2 ** attempt  # 2, 4, 8 seconds
                self.logger.info(
                    "agent_retrying",
                    agent=self.name,
                    attempt=attempt,
                    wait_time=wait_time
                )
                await asyncio.sleep(wait_time)
        
        # All retries failed
        self._failure_count += 1
        execution_time = (datetime.now() - start_time).total_seconds()
        self._total_execution_time += execution_time
        
        if progress_callback:
            await progress_callback(self.name, "failed", 0)
        
        raise last_error
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get agent execution statistics
        
        Returns:
            Statistics dictionary
        """
        avg_time = (
            self._total_execution_time / self._execution_count
            if self._execution_count > 0
            else 0
        )
        
        success_rate = (
            self._success_count / self._execution_count * 100
            if self._execution_count > 0
            else 0
        )
        
        return {
            "agent_name": self.name,
            "total_executions": self._execution_count,
            "successful": self._success_count,
            "failed": self._failure_count,
            "success_rate": f"{success_rate:.1f}%",
            "average_execution_time": f"{avg_time:.2f}s",
            "total_execution_time": f"{self._total_execution_time:.2f}s"
        }
    
    def reset_stats(self):
        """Reset execution statistics"""
        self._execution_count = 0
        self._success_count = 0
        self._failure_count = 0
        self._total_execution_time = 0.0


class AgentOrchestrator:
    """
    Orchestrates multiple agents in sequence or parallel
    """
    
    def __init__(self):
        self.agents: Dict[str, BaseAgent] = {}
        self.logger = structlog.get_logger("AgentOrchestrator")
    
    def register_agent(self, agent: BaseAgent):
        """
        Register an agent
        
        Args:
            agent: Agent instance to register
        """
        self.agents[agent.name] = agent
        self.logger.info("agent_registered", agent=agent.name)
    
    async def run_sequence(
        self,
        agent_names: list,
        input_data: Dict[str, Any],
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        Run agents in sequence (output of one becomes input of next)
        
        Args:
            agent_names: List of agent names to run in order
            input_data: Initial input data
            progress_callback: Optional progress callback
            
        Returns:
            Final output data
        """
        current_data = input_data
        results = {}
        
        for i, agent_name in enumerate(agent_names):
            if agent_name not in self.agents:
                raise ValueError(f"Agent '{agent_name}' not registered")
            
            agent = self.agents[agent_name]
            
            self.logger.info(
                "running_agent",
                agent=agent_name,
                step=f"{i+1}/{len(agent_names)}"
            )
            
            # Run agent
            result = await agent.run(current_data, progress_callback)
            results[agent_name] = result
            
            # Output becomes next input
            current_data = result
        
        return {
            "final_output": current_data,
            "all_results": results
        }
    
    async def run_parallel(
        self,
        agent_names: list,
        input_data: Dict[str, Any],
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        Run agents in parallel (all receive same input)
        
        Args:
            agent_names: List of agent names to run in parallel
            input_data: Input data for all agents
            progress_callback: Optional progress callback
            
        Returns:
            Dict of results keyed by agent name
        """
        tasks = []
        
        for agent_name in agent_names:
            if agent_name not in self.agents:
                raise ValueError(f"Agent '{agent_name}' not registered")
            
            agent = self.agents[agent_name]
            tasks.append(agent.run(input_data, progress_callback))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Package results
        output = {}
        for agent_name, result in zip(agent_names, results):
            if isinstance(result, Exception):
                output[agent_name] = {"error": str(result)}
            else:
                output[agent_name] = result
        
        return output
    
    def get_all_stats(self) -> Dict[str, Dict]:
        """
        Get statistics for all registered agents
        
        Returns:
            Dict of agent stats keyed by agent name
        """
        return {
            agent_name: agent.get_stats()
            for agent_name, agent in self.agents.items()
        }


# Example usage
if __name__ == "__main__":
    class ExampleAgent(BaseAgent):
        """Example agent implementation"""
        
        @property
        def name(self) -> str:
            return "ExampleAgent"
        
        @property
        def description(self) -> str:
            return "An example agent for testing"
        
        async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
            # Simulate work
            await asyncio.sleep(1)
            return {
                "output": f"Processed: {input_data.get('input', 'N/A')}"
            }
    
    async def test():
        agent = ExampleAgent()
        result = await agent.run({"input": "test data"})
        print(result)
        print(agent.get_stats())
    
    # asyncio.run(test())



