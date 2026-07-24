from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BaseModule(ABC):
    """Abstract base class for all enumeration/analysis modules."""

    @property
    @abstractmethod
    def module_name(self) -> str:
        """Name of the module."""
        pass

    @property
    @abstractmethod
    def supported_selector_types(self) -> List[str]:
        """Supported input types: 'email', 'username', 'phone', 'name'."""
        pass

    @abstractmethod
    async def check(self, target: str, selector_type: str) -> List[Dict[str, Any]]:
        """Run enumeration check and return list of raw hit dictionaries."""
        pass
