"""In-memory RAG over a hardcoded KFC menu.

The menu is embedded once at startup (OpenAI embeddings), vectors are held in
memory, and `search()` does cosine-similarity top-k. This backs the
`lookup_menu` function-calling tool: the agent calls the tool, we retrieve the
matching menu items (name, price, and stock), and the model weaves the result
into its spoken reply.

Stock matters for the demo: the Zinger Burger is in stock, the Chicken Piece is
out of stock — so the barge-in turn (order Zinger, then switch to chicken piece)
makes the agent's final reply say the chicken piece is unavailable, proving the
full tool round-trip drove the words it spoke.
"""

import json
import math
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.config import settings


EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_URL = "https://api.openai.com/v1/embeddings"


@dataclass
class MenuItem:
    name: str
    price: float
    in_stock: bool
    description: str

    def search_text(self) -> str:
        return f"{self.name}. {self.description}"

    def to_result(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "price": self.price,
            "in_stock": self.in_stock,
        }


# Hardcoded KFC menu. `in_stock` drives the demo: the Chicken Piece is
# deliberately out of stock so the barge-in switch surfaces it in the reply.
MENU: List[MenuItem] = [
    MenuItem("Zinger Burger", 5.99, True, "Spicy crispy chicken fillet burger with lettuce and mayo."),
    MenuItem("Chicken Piece", 2.49, False, "A single piece of our signature fried chicken, original recipe."),
    MenuItem("Fries", 2.99, True, "Regular portion of seasoned fries."),
    MenuItem("Coke", 1.99, True, "Chilled can of Coca-Cola."),
    MenuItem("Popcorn Chicken", 4.49, True, "Bite-sized pieces of crispy fried chicken."),
    MenuItem("Coleslaw", 1.79, True, "Creamy classic coleslaw side."),
    MenuItem("Twister Wrap", 4.99, True, "Crispy chicken strips wrapped with salad and sauce."),
    MenuItem("Hot Wings", 3.99, True, "Five spicy chicken wings."),
    MenuItem("Mighty Bucket", 14.99, True, "Shareable bucket with mixed fried chicken pieces and hot wings."),
    MenuItem("BBQ Chicken Burger", 6.49, True, "Crispy chicken fillet burger with smoky barbecue sauce and cheese."),
    MenuItem("Mashed Potatoes", 2.49, True, "Creamy mashed potatoes served with rich gravy."),
    MenuItem("Chocolate Chip Cookie", 1.49, True, "Soft baked chocolate chip cookie."),
    MenuItem("Strawberry Milkshake", 3.49, False, "Cold strawberry milkshake topped with whipped cream."),
    MenuItem("Chicken Tenders", 5.49, True, "Three boneless crispy chicken tenders with dipping sauce."),
]


def _embed(texts: List[str]) -> List[List[float]]:
    """Call the OpenAI embeddings REST endpoint with stdlib urllib (no extra deps)."""
    if not settings.openai_api_key:
        raise RuntimeError("Missing OPENAI_API_KEY for menu embeddings.")

    payload = json.dumps({"model": EMBEDDING_MODEL, "input": texts}).encode("utf-8")
    request = urllib.request.Request(
        EMBEDDING_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        body = json.loads(response.read().decode("utf-8"))

    # The API preserves input order in `data`, but sort by index to be safe.
    rows = sorted(body["data"], key=lambda row: row["index"])
    return [row["embedding"] for row in rows]


def _cosine(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class MenuIndex:
    """In-memory vector store over the menu. Embeds once, searches by cosine."""

    def __init__(self) -> None:
        self._vectors: Optional[List[List[float]]] = None

    @property
    def ready(self) -> bool:
        return self._vectors is not None

    def build(self) -> None:
        """Embed every menu line once and cache the vectors in memory."""
        if self._vectors is not None:
            return
        self._vectors = _embed([item.search_text() for item in MENU])

    def search(self, query: str, k: int = 3) -> List[Dict[str, Any]]:
        """Top-k menu items most similar to `query`, each as {name, price, in_stock}."""
        if not self._vectors:
            self.build()
        query_vec = _embed([query])[0]
        scored = [
            (_cosine(query_vec, vec), item)
            for vec, item in zip(self._vectors or [], MENU)
        ]
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [item.to_result() for _, item in scored[:k]]


menu_index = MenuIndex()
