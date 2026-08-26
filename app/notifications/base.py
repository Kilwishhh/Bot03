"""Notification contract independent of any messaging provider."""

from abc import ABC, abstractmethod


class Notifier(ABC):
    @abstractmethod
    def send(self, message: str) -> None:
        """Send a plain-text operational notification."""