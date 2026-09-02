"""Abstract storage port for Northstar Intent Graph persistence."""

from abc import ABC, abstractmethod
from typing import Optional

from northstar.core.entities import IntentNode
from northstar.core.graph import IntentGraph
from northstar.core.models import RelationshipEdge


class IntentRepository(ABC):
    """Abstract port for storing and retrieving intent graphs across deployment topologies."""

    @abstractmethod
    def load_graph(self) -> IntentGraph:
        """Load the complete intent graph from storage."""
        pass

    @abstractmethod
    def save_graph(self, graph: IntentGraph) -> None:
        """Persist the entire intent graph to storage."""
        pass

    @abstractmethod
    def save_node(self, node: IntentNode) -> None:
        """Save or update a single intent node."""
        pass

    @abstractmethod
    def save_edge(self, edge: RelationshipEdge) -> None:
        """Save or update a relational edge."""
        pass

