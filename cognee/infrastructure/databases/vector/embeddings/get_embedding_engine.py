from cognee.infrastructure.llm import get_llm_config
from .EmbeddingEngine import EmbeddingEngine
from .LiteLLMEmbeddingEngine import LiteLLMEmbeddingEngine

def get_embedding_engine() -> EmbeddingEngine:
    llm_config = get_llm_config()
    return LiteLLMEmbeddingEngine(api_key=llm_config.embedding_api_key, embedding_model=llm_config.embedding_model, embedding_dimensions=llm_config.embedding_dimensions)
