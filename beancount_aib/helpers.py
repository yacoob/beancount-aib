"""Helper functions for creating beancount Directives.

NOTE: beancount.core.data types are all NamedTuples, and they don't play well with static type checking :[
"""

import datetime
from decimal import Decimal
from typing import Optional

from beancount.core.data import (
    EMPTY_SET,
    Amount,
    Balance,
    Open,
    Posting,
    Transaction,
)

DEFAULT_CURRENCY = 'EUR'
DEFAULT_FLAG = '!'
EMPTY_TAGS = EMPTY_SET
EMPTY_LINKS = EMPTY_SET
EMPTY_META = {}


# All of those helper functions have short names and a set of
# sensible defaults within the importer context.


def Op(account: str, date: datetime.date, *, currency: str = DEFAULT_CURRENCY) -> Open:  # pyright: ignore reportInvalidTypeForm
    """Create an Open directive."""
    return Open(EMPTY_META, date, account, [currency], None)  # pyright: ignore reportCallIssue


def Bal(
    account: str,
    amount: str,
    date: datetime.date,
    *,
    currency: str = DEFAULT_CURRENCY,
    meta: Optional[dict[str, str]] = None,
):
    """Create a Balance directive."""
    return Balance(  # pyright: ignore reportCallIssue
        meta or EMPTY_META,
        date,
        account,
        Amount(Decimal(amount), currency),
        None,
        None,
    )


def Post(
    account: str,
    *,
    amount: Optional[str] = None,
    currency: Optional[str] = DEFAULT_CURRENCY,
) -> Posting:
    """Create a Posting object."""
    return Posting(
        account,
        Amount(Decimal(amount), currency) if amount else None,  # pyright: ignore reportArgumentType
        None,
        None,
        None,
        None,
    )


def Tx(  # noqa: PLR0913
    date: datetime.date,
    payee: Optional[str] = None,
    *,
    narration: Optional[str] = None,
    postings: Optional[list[Posting]] = None,
    flag: Optional[str] = DEFAULT_FLAG,
    tags: Optional[set[str]] = None,
    meta: Optional[dict[str, str]] = None,
):
    """Create a Transaction directive."""
    return Transaction(  # pyright: ignore reportCallIssue
        meta.copy() if meta else EMPTY_META,
        date,
        flag,
        payee.strip() if payee else '',
        narration.strip() if narration else '',
        tags.copy() if tags else EMPTY_TAGS,
        EMPTY_LINKS,
        postings if postings else [],
    )
