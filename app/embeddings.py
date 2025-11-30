# app/embeddings.py  (Google Vertex AI embeddings)
import os
from typing import List
from math import ceil

# Google Vertex AI client
from google.cloud import aiplatform
from google.auth import default as google_auth_default

# Configuration - replace model if you want another one
# Recommended models: "textembedding-gecko@001" (or check Vertex AI docs for latest)
EMBEDDING_MODEL = os.getenv("VERTEX_EMBEDDING_MODEL", "textembedding-gecko@001")
REGION = os.getenv("GOOGLE_CLOUD_REGION", "us-central1")
PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT")  # optional, picks up from credentials if not set

# Batch size - tune based on model/token limits and your latency budget
BATCH_SIZE = int(os.getenv("EMBED_BATCH_SIZE", "16"))


def _init_client():
    """
    Initialize Vertex AI client. Uses GOOGLE_APPLICATION_CREDENTIALS env var or ADC.
    """
    # If you need to explicitly set project/region, do it here:
    if PROJECT:
        aiplatform.init(project=PROJECT, location=REGION)
    else:
        aiplatform.init(location=REGION)
    # The client is created per call below using aiplatform.gapic because the high-level helpers
    # may not expose embeddings directly depending on the version.
    return aiplatform


def embed_texts(texts: List[str]) -> List[List[float]]:
    """
    Embed a list of texts using Vertex AI Embeddings API (textembedding-gecko@001 or similar)
    Returns: list of embedding vectors (list of floats).
    """
    if not texts:
        return []

    # initialize
    _init_client()

    # use low-level client for embeddings
    client = aiplatform.gapic.PredictionServiceClient()

    # Determine endpoint name for the model
    # Format for endpoint: projects/{project}/locations/{location}/publishers/google/models/{model}
    # BUT Vertex's managed embeddings can be called via "model" resource name like:
    # "projects/{project}/locations/{location}/publishers/google/models/{model}"
    project = PROJECT or os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project:
        # If not set, fall back to credentials' project if available
        try:
            _, default_project = google_auth_default()
            project = project or default_project
        except Exception:
            raise RuntimeError("Google project not set. Set GOOGLE_CLOUD_PROJECT env var or provide ADC.")

    model_name = EMBEDDING_MODEL
    # Construct model resource path
    model_resource = f"projects/{project}/locations/{REGION}/publishers/google/models/{model_name}"

    embeddings = []

    # Vertex may accept multiple instances per Predict call; still batch to avoid size limits.
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        instances = [{"content": t} for t in batch]

        response = client.predict(
            endpoint=model_resource,  # using model resource as endpoint-like arg
            instances=instances,
        )

        # response.predictions is a sequence; each prediction contains 'embedding' key (depends on model)
        for pred in response.predictions:
            # models may return embedding under 'embedding' or 'output' keys; handle common cases:
            if isinstance(pred, dict) and "embedding" in pred:
                vec = pred["embedding"]
            elif isinstance(pred, dict) and "output" in pred and isinstance(pred["output"], dict) and "embedding" in pred["output"]:
                vec = pred["output"]["embedding"]
            else:
                # if response item is a list/tuple or already the vector
                vec = pred
            embeddings.append([float(x) for x in vec])

    if len(embeddings) != len(texts):
        raise RuntimeError(f"Embedding count mismatch: expected {len(texts)}, got {len(embeddings)}")

    return embeddings
