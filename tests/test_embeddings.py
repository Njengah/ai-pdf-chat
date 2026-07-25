import asyncio

from backend.services.embeddings import chunk_pages, cosine_similarity, embed_texts
from backend.services.pdf_parser import PageText


def test_chunk_pages_overlap():
    pages = [PageText(page=1, text="a" * 1000)]
    chunks = chunk_pages(pages, chunk_size=400, chunk_overlap=50)
    assert len(chunks) >= 2
    assert all(c["page"] == 1 for c in chunks)


def test_local_embeddings_are_normalized():
    vectors = asyncio.run(
        embed_texts(["alpha beta", "alpha beta", "totally different topic"])
    )
    assert abs(sum(x * x for x in vectors[0]) - 1.0) < 1e-6
    assert cosine_similarity(vectors[0], vectors[1]) > 0.99
    assert cosine_similarity(vectors[0], vectors[2]) < cosine_similarity(vectors[0], vectors[1])
