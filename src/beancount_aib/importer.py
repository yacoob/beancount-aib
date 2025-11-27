"""Importer for AIB CSVs."""

import csv
import datetime
from copy import deepcopy
from functools import cache
from pathlib import Path
from typing import Any

from beancount.core import data
from beancount.core.data import Entries, Transaction, new_metadata
from beangulp import Importer as BeangulpImporter

from beancount_aib.extractors import AIB_EXTRACTORS
from beancount_tx_cleanup.cleaner import Extractors, TxnPayeeCleanup
from beancount_tx_cleanup.helpers import (
    Bal,
    Post,
    Tx,
)


class LineNoDictReader(csv.DictReader):
    """LineNoDictReader is a csv.DictReader that adds a line number to the result dicts."""

    def __next__(self):  # noqa: D105
        d = super().__next__()
        d['__lineno'] = self.line_num
        return d


@cache
def csv2rowlist(filepath: str) -> list[dict]:
    """csv2rowlist reads a CSV file from filepath and returns a list of dicts."""
    with open(filepath, encoding='UTF-8') as f:
        return list(LineNoDictReader(f, skipinitialspace=True))


class Importer(BeangulpImporter):
    """Parser for AIB CSVs adhering to beangulp.Importer interface.

    https://github.com/beancount/beangulp

    NOTE: all methods that return data (eg. `account` or `extract`)
    should always `self.identify(filepath)` first, as there's no guarantee
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
    We might cache the account name per `filepath` provided, but we're then exposed
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
        """Create new Importer instance.

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

    def identify(self, filepath: str) -> bool:
        """Verify whether Importer can handle given file."""
        # each row specifies account in the first field; check if it's the same across the whole file
        try:
            rows = csv2rowlist(filepath)
        except (OSError, csv.Error):
            return False
        if not rows:
            return False
        first_line_account = next(iter(rows[0].values()))
        if any(first_line_account != next(iter(row.values())) for row in rows):
            print(
                f'{Path(filepath).name} contains transactions for multiple accounts',
            )
            return False
        # check if this account is in the provided account map
        self.importer_account = self.account_map.get(
            first_line_account,
            self.default_account,
        )
        return first_line_account in self.account_map

    def date(self, filepath: str) -> datetime.date | None:
        """Return the date of the last transaction in the file.

        This date is treated as file's date, that is a date for which this file is representative.
        """
        if self.identify(filepath):
            last_row_date = csv2rowlist(filepath)[-1][
                'Posted Transactions Date'
            ].strip()
            return datetime.datetime.strptime(last_row_date, '%d/%m/%Y').date()
        return None

    def account(self, filepath: str) -> data.Account:
        """Return the name of the account whose transactions are present in the file."""
        if self.identify(filepath):
            return self.importer_account
        return self.default_account

    def _parse(self, filepath: str) -> tuple[Entries, dict[str, Any] | None]:
        """Read file, extract transactions."""
        entries: Entries = []
        last_balance: dict[str, Any] | None = None
        for row in csv2rowlist(filepath):
            # grab values from the csv row
            tags = set()
            meta = new_metadata(filepath, row['__lineno'])
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
                tags=frozenset(tags),
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

    def extract(self, filepath: str, existing: Entries) -> Entries:
        """Turn file into Entries, consulting existing entries as a reference."""
        if not self.identify(filepath):
            return []
        # parse the file content into a list of Directives, save last seen balance amount
        entries, last_balance = self._parse(filepath)
        # sort entries by transaction date
        entries.sort(key=lambda x: x.date)

        # use existing entries to reduce the amount of extracted transactions:
        # Beancount dedupes those further down the import pipeline, but that
        # still leaves them visible in the fava import interface.

        if self.cutoff_point is not None and existing:
            # find out latest existing transaction not flagged '!' for the self.importer_account
            latest_date = None
            for entry in reversed(existing):
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
