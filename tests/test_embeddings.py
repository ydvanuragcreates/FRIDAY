import pytest

from app.indexing.embeddings import EmbeddingProviderError, VoyageEmbeddingProvider


def test_voyage_provider_raises_clear_error_without_api_key() -> None:
    with pytest.raises(EmbeddingProviderError, match="VOYAGE_API_KEY"):
        VoyageEmbeddingProvider(api_key=None)


def test_voyage_provider_uses_known_dimensions_for_known_model() -> None:
    provider = VoyageEmbeddingProvider(api_key="fake-key", model="voyage-code-3")
    assert provider.dimensions == 1024


def test_voyage_provider_defaults_dimensions_for_unknown_model() -> None:
    provider = VoyageEmbeddingProvider(api_key="fake-key", model="some-future-model")
    assert provider.dimensions == 1024


def test_embed_documents_returns_empty_list_for_no_texts() -> None:
    provider = VoyageEmbeddingProvider(api_key="fake-key")
    assert provider.embed_documents([]) == []
