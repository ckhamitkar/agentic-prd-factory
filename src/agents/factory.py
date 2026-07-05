
import os
from typing import List, Any, Dict, Literal
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage
from .prompts import AGENT_PROMPTS, ALL_AGENT_PROMPTS
from .dev_prompts import DEV_AGENT_PROMPTS
from dotenv import load_dotenv
from src.tools.io import load_product_context

# Ensure env vars are loaded
load_dotenv()

# Provider type
ProviderType = Literal["anthropic", "gemini"]

# Default models for each provider
DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-4-20250514",
    "gemini": "gemini-2.0-flash-thinking-exp"
}


class LLMResponse:
    """Unified response class for all LLM providers."""
    def __init__(self, content: str):
        self.content = content


class AnthropicWrapper:
    """Wrapper for Anthropic Claude API."""

    def __init__(self, model_name: str = "claude-sonnet-4-20250514"):
        self.model_name = model_name
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY not found in environment. "
                "Please set it in your .env file."
            )

        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=api_key)
        except ImportError:
            raise ImportError(
                "anthropic package not installed. "
                "Run: pip install anthropic"
            )

    def invoke(self, messages: List[BaseMessage]) -> LLMResponse:
        """Invoke the Anthropic API with the given messages."""
        system_content = ""
        user_messages = []

        # Parse LangChain message format
        for m in messages:
            if isinstance(m, SystemMessage):
                system_content += m.content + "\n"
            elif isinstance(m, HumanMessage):
                user_messages.append({
                    "role": "user",
                    "content": m.content
                })

        # Anthropic API call
        response = self.client.messages.create(
            model=self.model_name,
            max_tokens=32000,
            system=system_content.strip() if system_content else None,
            messages=user_messages if user_messages else [{"role": "user", "content": ""}]
        )

        # Extract text from response
        content = ""
        for block in response.content:
            if hasattr(block, "text"):
                content += block.text

        return LLMResponse(content=content)


class GeminiWrapper:
    """Wrapper for Google Gemini API."""

    def __init__(self, model_name: str = "gemini-2.0-flash-exp"):
        self.model_name = model_name
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError(
                "GOOGLE_API_KEY not found in environment. "
                "Please set it in your .env file."
            )

        try:
            from google import genai
            self.client = genai.Client(api_key=api_key)
        except ImportError:
            raise ImportError(
                "google-genai package not installed. "
                "Run: pip install google-genai"
            )

    def invoke(self, messages: List[BaseMessage]) -> LLMResponse:
        """Invoke the Gemini API with the given messages."""
        system_instruction = ""
        last_user_message = ""

        # Simple parsing of one-shot prompt structure
        for m in messages:
            if isinstance(m, SystemMessage):
                system_instruction += m.content + "\n"
            elif isinstance(m, HumanMessage):
                last_user_message = m.content

        # Config with system instruction
        config = {
            'system_instruction': system_instruction
        }

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=last_user_message,
                config=config
            )
            return LLMResponse(content=response.text)
        except Exception as e:
            # Fallback if system_instruction fails or other error
            full_prompt = f"System Instruction:\n{system_instruction}\n\nUser Message:\n{last_user_message}"
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=full_prompt
                )
                return LLMResponse(content=response.text)
            except Exception as e2:
                raise e2


# Global provider setting (can be changed at runtime)
_current_provider: ProviderType = "anthropic"
_current_model: str = DEFAULT_MODELS["anthropic"]


def set_provider(provider: ProviderType, model: str = None):
    """Set the global LLM provider and model."""
    global _current_provider, _current_model
    if provider not in ["anthropic", "gemini"]:
        raise ValueError(f"Unknown provider: {provider}. Use 'anthropic' or 'gemini'.")
    _current_provider = provider
    _current_model = model or DEFAULT_MODELS[provider]


def get_provider() -> tuple:
    """Get the current provider and model."""
    return _current_provider, _current_model


class AgentFactory:
    """Factory for creating AI agents with configurable LLM backend."""

    def __init__(
        self,
        provider: ProviderType = None,
        model_name: str = None
    ):
        """
        Initialize the AgentFactory.

        Args:
            provider: LLM provider ("anthropic" or "gemini"). Defaults to global setting.
            model_name: Model name to use. Defaults to provider's default model.
        """
        # Store explicit overrides, or None to use global settings
        self._explicit_provider = provider
        self._explicit_model = model_name

        # Load the product context once at factory init
        self._product_context = load_product_context()

    @property
    def provider(self) -> str:
        """Get the current provider (explicit or global)."""
        return self._explicit_provider or _current_provider

    @property
    def model_name(self) -> str:
        """Get the current model name (explicit or global default)."""
        if self._explicit_model:
            return self._explicit_model
        return _current_model or DEFAULT_MODELS[self.provider]

    def create_agent(self, agent_name: str):
        """Create an agent with appropriate system prompt based on agent type."""
        if agent_name not in ALL_AGENT_PROMPTS:
            raise ValueError(f"Agent '{agent_name}' not found in registry.")

        prompt_config = ALL_AGENT_PROMPTS[agent_name]

        # Use specialized prompt builder for dev agents
        if agent_name in DEV_AGENT_PROMPTS:
            system_prompt = self._build_dev_agent_prompt(prompt_config, agent_name=agent_name)
        else:
            system_prompt = self._build_prd_agent_prompt(prompt_config, agent_name=agent_name)

        # Create appropriate wrapper based on provider
        llm = self._create_llm_wrapper()

        return system_prompt, llm

    def _create_llm_wrapper(self):
        """Create the appropriate LLM wrapper based on provider setting."""
        if self.provider == "anthropic":
            return AnthropicWrapper(self.model_name)
        elif self.provider == "gemini":
            return GeminiWrapper(self.model_name)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    def _product_context_block(self, agent_name: str) -> str:
        """Build the product-context block injected into every agent prompt."""
        block = (
            "\n\n## Product Context\n"
            "Evaluate every idea, feature, and recommendation against the product "
            "context below.\n\n"
            f"{self._product_context}\n"
        )
        return block

    def _build_prd_agent_prompt(self, config: Dict[str, Any], agent_name: str = "") -> str:
        """Build system prompt for PRD phase agents."""
        base = (
            f"You are the {config['role']}.\n"
            f"Focus: {config['focus']}.\n"
            f"Description: {config['description']}\n\n"
            "Your goal is to contribute to the PRD and other documents based on your expertise.\n"
            "In Round 1, you draft your section.\n"
            "In Round 2, you review others' work and negotiate to reach consensus.\n"
            "The Product Owner is the final decision maker."
        )
        base += self._product_context_block(agent_name)
        return base

    def _build_dev_agent_prompt(self, config: Dict[str, Any], agent_name: str = "") -> str:
        """Build system prompt for development phase agents."""
        prompt = (
            f"You are the {config['role']}.\n"
            f"Focus: {config['focus']}.\n"
            f"Description: {config['description']}\n\n"
            "Your goal is to produce high-quality, production-ready artifacts.\n"
            "Follow best practices and ensure your output is complete and functional.\n"
        )

        # Add code conventions if present
        if "code_conventions" in config:
            prompt += "\n## Code Conventions\n"
            for key, value in config["code_conventions"].items():
                prompt += f"- {key}: {value}\n"

        # Add expected output formats if present
        if "output_format" in config:
            prompt += "\n## Expected Output Formats\n"
            for key, value in config["output_format"].items():
                prompt += f"- {key}: {value}\n"

        # Add capabilities summary
        if "capabilities" in config:
            prompt += "\n## Your Capabilities\n"
            prompt += ", ".join(config["capabilities"]) + "\n"

        prompt += self._product_context_block(agent_name)
        return prompt

    def get_agent_config(self, agent_name: str) -> Dict[str, Any]:
        """Get the full configuration for an agent."""
        return ALL_AGENT_PROMPTS.get(agent_name)

    def is_dev_agent(self, agent_name: str) -> bool:
        """Check if an agent is a development phase agent."""
        return agent_name in DEV_AGENT_PROMPTS

    def get_prd_agents(self) -> List[str]:
        """Get list of PRD phase agent names."""
        return list(AGENT_PROMPTS.keys())

    def get_dev_agents(self) -> List[str]:
        """Get list of development phase agent names."""
        return list(DEV_AGENT_PROMPTS.keys())
