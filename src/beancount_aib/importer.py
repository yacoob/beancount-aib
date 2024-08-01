"""Importer for AIB CSVs."""

import csv
import datetime
from copy import deepcopy
from functools import cache
from typing import Any

from beancount.core.data import Entries, Transaction, new_metadata
from beancount.ingest.cache import _FileMemo as FileMemo
from beancount.ingest.importer import ImporterProtocol

from beancount_aib.extractors import AIB_EXTRACTORS
from beancount_tx_cleanup.cleaner import Extractors, TxnPayeeCleanup
from beancount_tx_cleanup.helpers import (
    Bal,
    Post,
    Tx,
)


class LineNoDictReader(csv.DictReader):
    """LineNoDictReader is a csv.DictReader that adds a __lineno entry to parsed dict indicating position of the data that formed this dict in the source file."""

    def __next__(self):  # noqa: D105
        d = super().__next__()
        d['__lineno'] = self.line_num
        return d


@cache
def csv2rowlist(file) -> list[dict]:
    """Cacheable file reader.

    Caching Importer.read(self, file) causes cache key to include
    Importer instance, which is a memory leak recipe.

    """
    return list(
        LineNoDictReader(file.contents().split('\n'), skipinitialspace=True),
    )


class Importer(ImporterProtocol):
    """Parser for AIB CSVs adhering to beancount.ingest.importer.ImporterProtocol.

    https://github.com/beancount/beancount/blob/v2/beancount/ingest/importer.py

    NOTE: all methods that return data (eg. `file_account` or `extract`)
    should always `self.identify(file)` first, as there's no guarantee
    that `self.importer_account` is up to date. Fava session might go like this:
    ```
    - identify(file1)
    - identify(file2)
    - account(file1)
    - account(file2)
    - [user clicks on 'import' for file1]
    - extract(file1)
    - [import happens with the value of `self.importer_account` set
      via `account(file2)` :| ]
    ```
    We might cache the account name per `file` provided, but we're then exposed
    to a situation where the file content will change without us realizing...
    Those CSV files are small, let's throw CPU at the problem :D
    """

    currency = 'EUR'
    file_encoding = 'UTF-8'
    txflag = '!'
    default_account = '__UNKNOWN__'
    default_narration = ''

    def __init__(
        self,
        account_map: dict[str, str],
        extractors: Extractors | None = None,
        cutoff_days: int | None = None,
    ):
        """Create new Importer instance, part of ImporterProtocol.

        - account_map maps account names present in the CSV file to account names used by beancount
        - if set, `cutoff_days` will drop all incoming transactions older than latest existing
          transaction for this account minus cutoff_point days
        """
        self.importer_account = self.default_account
        self.account_map = account_map
        if extractors is None:
            extractors = deepcopy(AIB_EXTRACTORS)
        self.extractors = extractors
        self.cutoff_point = None
        if cutoff_days is not None:
            self.cutoff_point = datetime.timedelta(days=cutoff_days)

    @staticmethod
    def read(file) -> list[dict]:  # noqa: D102
        return csv2rowlist(file)

    def identify(self, file: FileMemo) -> bool:
        """Verify whether Importer can handle given file; part of ImporterProtocol."""
        # does this file contain an actual csv content?
        if file.mimetype() != 'text/csv':
            return False
        # each row specifies account in the first field; check if it's the same across the whole file
        rows = self.read(file)
        first_line_account = next(iter(rows[0].values()))
        if any(first_line_account != next(iter(row.values())) for row in rows):
            print(f'{file.name} contains transactions for multiple accounts')
            return False
        # check if this account is in the provided account map
        self.importer_account = self.account_map.get(
            first_line_account,
            self.default_account,
        )
        return first_line_account in self.account_map

    def file_date(self, file) -> datetime.date | None:
        """Return the date of the last transaction in the file; part of ImporterProtocol.

        This date is treated as file's date, that is a date for which this file is representative.
        """
        if self.identify(file):
            last_row_date = self.read(file)[-1][
                'Posted Transactions Date'
            ].strip()
            return datetime.datetime.strptime(last_row_date, '%d/%m/%Y').date()
        return None

    def file_account(self, file) -> str:
        """Return the name of the account whose transactions are present in the file; part of ImporterProtocol."""
        if self.identify(file):
            return self.importer_account
        return self.default_account

    def _parse(self, file) -> tuple[Entries, dict[str, Any] | None]:
        """Read file, extract transactions."""
        entries: Entries = []
        last_balance: dict[str, Any] | None = None
        for row in self.read(file):
            # grab values from the csv row
            tags = set()
            meta = new_metadata(file.name, row['__lineno'])
            txdate = row['Posted Transactions Date'].strip()
            txdate = datetime.datetime.strptime(txdate, '%d/%m/%Y').date()
            if 'Description' in row:
                payee = row['Description']
            else:
                payee = ' '.join(
                    [
                        row['Description1'].strip(),
                        row['Description2'].strip(),
                        row['Description3'].strip(),
                    ],
                )
            payee = payee.strip()
            if row['Transaction Type'] == 'Credit':
                amount = row['Credit Amount']
            else:
                amount = '-' + row['Debit Amount']
            amount = amount.replace(',', '').strip()
            # handle foreign currency information if available
            # NOTE: Fields involved are filled in as expected only in credit card CSVs.
            # For current accounts, the fields are present, but the data is invalid; and
            # the currency and foreign amount are present in the description.
            if (c := row.get('Local Currency', self.currency)) != self.currency:
                tags.add(c.lower())
                meta['foreign-amount'] = row['Local Currency Amount'].strip()

            # create a new Transaction, with a single Posting for the account we're processing
            txn = Tx(
                date=txdate,
                payee=payee,
                narration=self.default_narration,
                flag=self.txflag,
                meta=meta,
                tags=tags,
                postings=[
                    Post(
                        self.importer_account,
                        amount=amount,
                        currency=self.currency,
                    ),
                ],
            )
            # apply cleanups, extract metadata
            if self.extractors:
                txn = TxnPayeeCleanup(
                    txn,
                    self.extractors,
                    preserveOriginalIn='original-payee',
                )
            entries.append(txn)
            # update last seen balance
            if balance := row.get('Balance', None):
                last_balance = {
                    'date': txdate,
                    'balance': balance.strip(),
                    'meta': meta,
                }
        return entries, last_balance

    def extract(self, file, existing_entries: Entries | None = None) -> Entries:
        """Turn file into Entries, consulting existing_entries as a reference; part of ImporterProtocol."""
        if not self.identify(file):
            return []
        # parse the file conteint into a list of Directives, save last seen balance amount
        entries, last_balance = self._parse(file)
        # sort entries by transaction date
        entries.sort(key=lambda x: x.date)

        # use existing_entries to reduce the amount of extracted transactions:
        # Beancount dedupes those further down the import pipeline, but that
        # still leaves them visible in the fava import interface.

        if self.cutoff_point is not None and existing_entries is not None:
            # find out latest existing transaction not flagged '!' for the self.importer_account
            latest_date = None
            for entry in reversed(existing_entries):
                if not isinstance(entry, Transaction):
                    continue
                if entry.flag == '!':
                    continue
                if any(
                    p.account == self.importer_account for p in entry.postings
                ):
                    latest_date = entry.date
                    break

            # remove all entries happening earlier than self.overlap_days before that
            if latest_date:
                entries = [
                    e
                    for e in entries
                    if e.date >= (latest_date - self.cutoff_point)
                ]

        # add a balance entry at the end
        if last_balance:
            date = last_balance['date'] + datetime.timedelta(days=1)
            entries.append(
                Bal(
                    self.importer_account,
                    last_balance['balance'],
                    date,
                    currency=self.currency,
                    meta=last_balance['meta'],
                ),
            )
        return entries
