from abc import ABC, abstractmethod
from typing import Any


class DatabaseInterface(ABC):

    @abstractmethod
    def connect(self) -> None:
        pass

    @abstractmethod
    def query(self, query: str, params: Any = None) -> Any:
        pass

    @abstractmethod
    def close(self) -> None:
        pass 

