"""Tests for the categorizer."""

import datetime
import re
from typing import ClassVar

from beancount.core.data import Directive, Transaction

from beancount_aib.categorizer import PayeeCategorizer
from beancount_tx_cleanup.helpers import Post, Tx


class TestPayeeCategorizer:
    """All categorizer tests."""

    account = 'Assets:AIB:Checking'
    categories: ClassVar[dict[str, list[str]]] = {
        'Expenses:Groceries': ['tesco', 'lidl'],
        'Expenses:Restaurants': ['the winding', 'zaytoon'],
    }
    categorizer = PayeeCategorizer(categories)
    # transactions to be categorized
    txs: tuple[Directive, ...] = (
        # grocery shopping at Tesco
        # should be categorized as Groceries
        Tx(datetime.date(2099, 1, 1), 'TESCO STORES 7', postings=[Post(account, amount='42.99')]),
        # visit to Zaytoon
        # should be categorized as Restaurants
        Tx(datetime.date(2099, 1, 2), 'Zaytoon North', postings=[Post(account, amount='13.33')]),
        # tool purchase at Woodie's
        # this tx has two postings already and should be left unmodified
        Tx(datetime.date(2099, 1, 3), 'Woodies', postings=[Post(account, amount='50.12'), Post('Expenses:Household', amount='-50.12')]),
        # dining at The Winding Stairs
        # should be categorized as Restaurants
        Tx(datetime.date(2099, 1, 4), 'The Winding Stairs', postings=[Post(account, amount='67.23')]),
        # manga buying at The Forbidden Planet
        # this tx doesn't match any predefined rules and should be left unmodified
        Tx(datetime.date(2099, 1, 5), 'forbidden planet', postings=[Post(account, amount='18.81')]),
    )  # fmt: skip

    def test_creation(self):
        """Check whether REs used for payee matching are created correctly."""
        assert self.categorizer.categories == {
            'Expenses:Groceries': re.compile(r'(?i)^(tesco|lidl).*'),
            'Expenses:Restaurants': re.compile(r'(?i)^(the winding|zaytoon).*'),
        }

    def test_categorization(self):
        """Run a set of txs through categorizer, verify added postings."""
        processed_txs = [
            tx
            for tx in self.categorizer(None, None, list(self.txs), None)
            if isinstance(tx, Transaction)
        ]
        assert len(processed_txs) == 5  # noqa: PLR2004
        expected_categories = [
            'Expenses:Groceries',     # Tesco shopping
            'Expenses:Restaurants',   # Zaytoon
            'Expenses:Household',     # Woodie's
            'Expenses:Restaurants',   # The Winding Stairs
            self.account,             # Forbidden Planet ("last" posting is the outgoing one)
        ]  # fmt: skip
        for t, c in zip(processed_txs, expected_categories, strict=True):
            assert t.postings[-1].account == c
