'''Adapter for Generic API LLM provider API'''
import asyncio
from typing import List, Type
from pydantic import BaseModel
import instructor
import openai

from cognee.exceptions import InvalidValueError
from cognee.infrastructure.llm.llm_interface import LLMInterface
from cognee.infrastructure.llm.prompts import read_query_prompt
from cognee.shared.data_models import MonitoringTool
from cognee.base_config import get_base_config
from cognee.infrastructure.llm.config import get_llm_config


class GenericAPIAdapter(LLMInterface):
    """Adapter for Generic API LLM provider API """
    name: str
    model: str
    api_key: str

    def __init__(self, api_endpoint, api_key: str, model: str, name: str):
        self.name = name
        self.model = model
        self.api_key = api_key

        llm_config = get_llm_config()

        if llm_config.llm_provider == "groq":
            from groq import groq
            self.aclient = instructor.from_openai(
                client = groq.Groq(
                  api_key = api_key,
                ),
                mode = instructor.Mode.MD_JSON
            )
        else:
            base_config = get_base_config()

            if base_config.monitoring_tool == MonitoringTool.LANGFUSE:
                from langfuse.openai import AsyncOpenAI
            elif base_config.monitoring_tool == MonitoringTool.LANGSMITH:
                from langsmith import wrappers
                from openai import AsyncOpenAI
                AsyncOpenAI = wrappers.wrap_openai(AsyncOpenAI())
            else:
                from openai import AsyncOpenAI

            self.aclient = instructor.patch(
                AsyncOpenAI(
                    base_url = api_endpoint,
                    api_key = api_key,  # required, but unused
                ),
                mode = instructor.Mode.JSON,
            )

    async def acreate_structured_output(self, text_input: str, system_prompt: str, response_model: Type[BaseModel]) -> BaseModel:
        """Generate a response from a user query."""

        return await self.aclient.chat.completions.create(
            model = self.model,
            messages = [
                {
                    "role": "user",
                    "content": f"""Use the given format to
                    extract information from the following input: {text_input}. """,
                },
                {"role": "system", "content": system_prompt},
            ],
            response_model = response_model,
        )

    def show_prompt(self, text_input: str, system_prompt: str) -> str:
        """Format and display the prompt for a user query."""
        if not text_input:
            text_input = "No user input provided."
        if not system_prompt:
            raise InvalidValueError(message="No system prompt path provided.")
        system_prompt = read_query_prompt(system_prompt)

        formatted_prompt = f"""System Prompt:\n{system_prompt}\n\nUser Input:\n{text_input}\n""" if system_prompt else None
        return formatted_prompt
