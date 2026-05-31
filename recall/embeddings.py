from google import genai
from google.genai import types

from recall.config import Config


def embed(text: str, cfg: Config, task_type: str = "RETRIEVAL_DOCUMENT") -> list[float]:
    client = genai.Client(api_key=cfg.gemini_api_key)
    response = client.models.embed_content(
        model=cfg.embed_model,
        contents=text,
        config=types.EmbedContentConfig(
            task_type=task_type,
            output_dimensionality=cfg.embed_dim,
        ),
    )
    return list(response.embeddings[0].values)
