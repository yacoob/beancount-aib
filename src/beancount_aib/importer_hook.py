"""My own version of the ImporterHook from smart-importer.

I use this to avoid having a dependency on the smart-importer
project, as all I need is a class definition with a single method.
"""

from typing import Protocol


class ImporterHookProtocol(Protocol):
    """smart_importer.ImporterHook look-a-like."""

    def __call__(
        self,
        importer,
        file,
        imported_entries,
        existing_entries,
    ) -> list:
        """Apply the hook."""
        ...
