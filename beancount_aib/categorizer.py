"""Local variant of bratekarate/beancount-categorizer."""

import re

from beancount.core.data import Directive, Entries, Transaction
from beancount.ingest.cache import _FileMemo as FileMemo
from beancount.ingest.importer import ImporterProtocol
from beancount_tx_cleanup.helpers import Post
from smart_importer.hooks import ImporterHook


class PayeeCategorizer(ImporterHook):
    """PayeeCategorizer is pretty much https://github.com/bratekarate/beancount-categorizer.

    I've cleaned it up, modified a bit, sprinkled with type annotations, and added tests.
    I didn't want to have an unreleased code dependency.
    Thanks bratekarate! :)
    """

    def __init__(self, categories: dict[str, list[str]]):  # noqa: D107
        self.categories = {
            account: re.compile(r'(?i)^(' + '|'.join(names) + r').*')
            for account, names in categories.items()
        }

    def __call__(  # noqa: D102
        self,
        _importer: ImporterProtocol | None,
        _file: FileMemo | None,
        imported_entries: Entries,
        _existing_entries: Entries | None,
    ) -> Entries:
        return [self._process(entry) for entry in imported_entries]

    def _process(self, entry: Directive) -> Directive:
        if type(entry) is Transaction and len(entry.postings) == 1:
            for account, regexp in self.categories.items():
                if regexp.match(entry.payee):
                    entry.postings.append(Post(account))
                    break
        return entry
