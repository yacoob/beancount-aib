"""Local variant of bratekarate/beancount-categorizer."""

import re

from beancount.core.data import Directive, Entries, Transaction

from beancount_tx_cleanup.helpers import Post


class PayeeCategorizer:
    """PayeeCategorizer was initially borrowed from https://github.com/bratekarate/beancount-categorizer.

    I've cleaned it up, modified a bit, sprinkled with type annotations, and
    added tests. I didn't want to have an unreleased code dependency.
    Thanks bratekarate!

    And then, as it happens, it started to mutate over time :D
    """

    def __init__(self, categories: dict[str, list[str]]):  # noqa: D107
        self.categories = {
            account: re.compile(r'(?i)^(' + '|'.join(names) + r').*')
            for account, names in categories.items()
        }

    def __call__(  # noqa: D102
        self,
        extracted_entries: Entries,
        _existing_entries: Entries | None = None,
    ) -> Entries:
        return [self._process(entry) for entry in extracted_entries]

    def _process(self, entry: Directive) -> Directive:
        if type(entry) is Transaction and len(entry.postings) == 1:
            for account, regexp in self.categories.items():
                if entry.payee and regexp.match(entry.payee):
                    entry.postings.append(Post(account))
                    break
        return entry
