"""Download the local multilingual embedding model; no API key is needed."""
from sentence_transformers import SentenceTransformer
from services.api.bijaksense.config import EMBEDDING_MODEL

if __name__ == '__main__':
    model = SentenceTransformer(EMBEDDING_MODEL, device='cpu', trust_remote_code=False)
    print('BijakSense local embedding model ready:', EMBEDDING_MODEL)
