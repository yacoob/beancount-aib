"""Tests for the importer itself."""

import datetime
import tempfile
from io import StringIO
from pathlib import Path
from typing import ClassVar

import pytest
from beancount.core.data import Balance, Transaction

from beancount_aib.importer import Importer, LineNoDictReader, csv2rowlist
from beancount_tx_cleanup.cleaner import Extractors
from beancount_tx_cleanup.helpers import Bal, Post, Tx


@pytest.fixture
def filecontents(request):
    """Provide the string from filecontents mark.

    Both leading and trailing whitespace are trimmed from the content
    """
    marker_content = None
    if marker := request.node.get_closest_marker('filecontents'):
        marker_content = marker.args[0]
    content = marker_content or ''
    return content.strip()


@pytest.fixture
def input_file(filecontents):
    """Provide the filecontents mark as a standard file object."""
    return StringIO(filecontents)


@pytest.fixture
def input_filepath(filecontents, tmp_path, request):
    """Provide the filecontents mark as a temporary file path for beangulp importers."""
    test_file = tmp_path / f"{request.node.name}.csv"
    test_file.write_text(filecontents, encoding='UTF-8')
    return str(test_file)


class TestLineNoDictReader:
    """Tests related to LineNoDictReader."""

    FILECONTENTS = """
lead,support,support2,support3
Picard,Data,Worf,Troi
Mal,Zoe,Kaylee,Wash
Abed,Troy,Britta,Shirley
Bojack,Diane,Princess Carolyn,Todd
"""

    PARSED_DICTS: ClassVar[list[dict[str, str | int]]] = [
        {
            '__lineno': 2,
            'lead': 'Picard',
            'support': 'Data',
            'support2': 'Worf',
            'support3': 'Troi',
        },
        {
            '__lineno': 3,
            'lead': 'Mal',
            'support': 'Zoe',
            'support2': 'Kaylee',
            'support3': 'Wash',
        },
        {
            '__lineno': 4,
            'lead': 'Abed',
            'support': 'Troy',
            'support2': 'Britta',
            'support3': 'Shirley',
        },
        {
            '__lineno': 5,
            'lead': 'Bojack',
            'support': 'Diane',
            'support2': 'Princess Carolyn',
            'support3': 'Todd',
        },
    ]

    @pytest.mark.filecontents(FILECONTENTS)
    def testLineNoDictReader(self, input_file):
        """Test reading CSV file into a dict with linenumber information."""
        assert list(LineNoDictReader(input_file)) == self.PARSED_DICTS

    @pytest.mark.filecontents(FILECONTENTS)
    def test_csv2rowlist(self, input_filepath):
        """Test reading CSV files via csv2rowlist."""
        assert csv2rowlist(input_filepath) == self.PARSED_DICTS


class TestImporter:
    """Tests for the importer.

    Those tests focus on importer's functionality - eg. file recognition,
    parsing, etc. For full coverage, you need a beancount regression test with a recent data set.

    """

    account_map: ClassVar[dict[str, str]] = {'111': 'Assets:AIB:Secret'}
    importer = Importer(account_map)

    def T(
        self,
        n: int,
        p: str,
        a: str,
        m: dict[str, str] | None = None,
        t: set[str] | None = None,
        filepath: str | None = None,
    ) -> Transaction:
        """Transaction-maker helper."""
        m = m or {}
        t = t or set()
        # Use provided filepath or a placeholder for tests that don't pass it
        filename = filepath if filepath else '<test-file>'
        return Tx(
            datetime.date(2063, 1, n),
            p,
            postings=[Post('Assets:AIB:Secret', amount=a)],
            meta={
                'filename': filename,
                'lineno': n + 1,
                **m,
            },
            tags=frozenset(t),
        )

    def B(self, n, a, filepath: str | None = None) -> Balance:
        """Balance-maker helper."""
        filename = filepath if filepath else '<test-file>'
        return Bal(
            'Assets:AIB:Secret',
            a,
            datetime.date(2063, 1, n),
            meta={'filename': filename, 'lineno': n},
        )

    @pytest.mark.filecontents("""
    absolutely: not a csv file
    more: 42
    """)
    def test_not_a_csv_file(self, input_filepath):
        """Importer should not be able to parse a non-CSV file."""
        assert not self.importer.identify(input_filepath)
        assert self.importer.date(input_filepath) is None
        assert (
            self.importer.account(input_filepath)
            == self.importer.default_account
        )
        assert self.importer.extract(input_filepath, []) == []

    @pytest.mark.filecontents("""
    Posted Account, Posted Transactions Date, Description1, Description2, Description3, Debit Amount, Credit Amount,Balance,Posted Currency,Transaction Type,Local Currency Amount,Local Currency
    "111","01/01/2063","Nuts and Bolts","Limited","","23.50",,"126.50",EUR,"Debit","23.50",EUR
    "111","02/01/2063","VDP-Croissants","","","10.00",,"116.50",EUR,"Debit","10.00",EUR
    "111","03/01/2063","twenty feet of pure","white snow","",,"200.00","316.50",EUR,"Credit","200.00",EUR
    """)
    def test_current_account(self, input_filepath):
        """Test parsing a CSV export from a current account."""
        assert self.importer.identify(input_filepath)
        assert self.importer.date(input_filepath) == datetime.date(2063, 1, 3)
        assert self.importer.account(input_filepath) == self.account_map['111']
        assert self.importer.extract(input_filepath, []) == [
            self.T(1, 'Nuts and Bolts Limited', '-23.50', filepath=input_filepath),
            self.T(
                2,
                'Croissants',
                '-10.00',
                {'original-payee': 'VDP-Croissants'},
                {'point-of-sale'},
                filepath=input_filepath,
            ),
            self.T(3, 'twenty feet of pure white snow', '200.00', filepath=input_filepath),
            self.B(4, '316.50', filepath=input_filepath),
        ]

    @pytest.mark.filecontents("""
    Masked Card Number, Posted Transactions Date, Description, Debit Amount, Credit Amount, Posted Currency, Transaction Type, Local Currency Amount, Local Currency
    "111","01/01/2063","Bagel Factory", "21.02 ","  ","GBP","Debit"," 17.56 ","GBP"
    "111","02/01/2063","FreeNow", "16.80","  ","EUR","Debit"," 16.8 ","EUR"
    "111","03/01/2063","twenty feet of pure white snow","0.00 "," 1310.00 ","EUR","Credit"," 1310.0","EUR"
    """)
    def test_cc_acount(self, input_filepath):
        """Test parsing a CSV export from a credit card account."""
        assert self.importer.identify(input_filepath)
        assert self.importer.date(input_filepath) == datetime.date(2063, 1, 3)
        assert self.importer.account(input_filepath) == self.account_map['111']
        assert self.importer.extract(input_filepath, []) == [
            self.T(
                1,
                'Bagel Factory',
                '-21.02',
                m={'foreign-amount': '17.56'},
                t={'gbp'},
                filepath=input_filepath,
            ),
            self.T(2, 'FreeNow', '-16.80', filepath=input_filepath),
            self.T(3, 'twenty feet of pure white snow', '1310.00', filepath=input_filepath),
        ]

    @pytest.mark.filecontents("""
    Masked Card Number, Posted Transactions Date, Description, Debit Amount, Credit Amount, Posted Currency, Transaction Type, Local Currency Amount, Local Currency
    "111","01/01/2063","Bagel Factory", "21.02 ","  ","GBP","Debit"," 17.56 ","GBP"
    """)
    def test_cc_with_no_extractors(self, input_filepath):
        """Parse a cc export, but with an empty Extractor list."""
        importer = Importer(self.account_map, Extractors())
        assert importer.identify(input_filepath)
        assert importer.date(input_filepath) == datetime.date(2063, 1, 1)
        assert importer.account(input_filepath) == self.account_map['111']
        assert importer.extract(input_filepath, []) == [
            self.T(
                1,
                'Bagel Factory',
                '-21.02',
                m={'foreign-amount': '17.56'},
                t={'gbp'},
                filepath=input_filepath,
            ),
        ]

    @pytest.mark.filecontents("""
    111,x,y
    111,a,b
    111,c,d
    999,e,f
    111,g,h
    """)
    def test_multiple_accounts_file(self, input_filepath):
        """Importer doesn't handle a CSV file containing transactions for multiple accounts."""
        assert not self.importer.identify(input_filepath)
        assert self.importer.date(input_filepath) is None
        assert (
            self.importer.account(input_filepath)
            == self.importer.default_account
        )
        assert self.importer.extract(input_filepath, []) == []

    @pytest.mark.filecontents("""
    999,x,y
    999,a,b
    999,c,d
    999,e,f
    999,g,h
    """)
    def test_account_not_in_map(self, input_filepath):
        """Importer doesn't handle accounts that are not configured via account_map."""
        assert not self.importer.identify(input_filepath)
        assert self.importer.date(input_filepath) is None
        assert (
            self.importer.account(input_filepath)
            == self.importer.default_account
        )
        assert self.importer.extract(input_filepath, []) == []


@pytest.mark.filecontents("""
Posted Account, Posted Transactions Date, Description1, Description2, Description3, Debit Amount, Credit Amount,Balance,Posted Currency,Transaction Type,Local Currency Amount,Local Currency
"111","01/01/2063","nine golden rings","","","9.99",,"1200.00",EUR,"Debit"," 9.99",EUR
"111","02/01/2063","ring wraith costume","","","200.00",,"1000.00",EUR,"Debit"," 200.00",EUR
"111","03/01/2063","stick horse","","","300.00",,"700.00",EUR,"Debit"," 300.00",EUR
"111","04/01/2063","ACME hobbit trap","","","50.00",,"650.00",EUR,"Debit"," 50.00",EUR
"111","05/01/2063","stick wyvern","","","400.00",,"250.00",EUR,"Debit"," 400.00",EUR
""")
class TestImporterCutoff:
    """These tests excercise culling in situations where the imported txs overlap with the existing ones.

    All of the tests in TestImporterCutoff use the file content from
    the filecontents mark on the class itself. An empty list of Extractors
    is explicitly provided to the cleaner, as we don't really care about
    the Extractors' transformations in this test.
    """

    ACCOUNT_NAME = 'Assets:AIB:Secret'
    ACCOUNT_MAP: ClassVar[dict[str, str]] = {'111': ACCOUNT_NAME}
    FULL_IMPORT_DIRECTIVE_LENGTH = 6  # 5 txs + balance directive

    @pytest.fixture
    def existing_entries(self):
        """Provide a set of existing txs. Modify as needed in each test."""

        def d(day):
            return datetime.date(2063, 1, day)

        return [
            Tx(d(1), 'nine golden rings', flag='*', postings=[Post(self.ACCOUNT_NAME, amount='-9.99')]),
            Tx(d(2), 'ring wraith costume', flag='*', postings=[Post(self.ACCOUNT_NAME, amount='-200.00')]),
            Tx(d(2), 'Nazgul meetup', flag='!', postings=[Post('Assets:Cash', amount='-20.00')]),
            Tx(d(3), 'stick horse', flag='*', postings=[Post(self.ACCOUNT_NAME, amount='-300.00')]),
            Bal(self.ACCOUNT_NAME, '700', datetime.date(2063, 1, 4)),
        ]  # fmt: skip

    def test_cutoff_nonzero(self, input_filepath, existing_entries):
        """Remove txs older than one day before oldest existing tx for the account in question."""
        txs = Importer(self.ACCOUNT_MAP, Extractors(), cutoff_days=1).extract(input_filepath, existing_entries)  # fmt: skip
        assert len(txs) == self.FULL_IMPORT_DIRECTIVE_LENGTH - 1
        assert txs[0].date == datetime.date(2063, 1, 2)
        assert txs[-1].date == datetime.date(2063, 1, 6)

    def test_cutoff_zero(self, input_filepath, existing_entries):
        """Remove txs older than the oldest existing tx for the account in question."""
        txs = Importer(self.ACCOUNT_MAP, Extractors(), cutoff_days=0).extract(input_filepath, existing_entries)  # fmt: skip
        assert len(txs) == self.FULL_IMPORT_DIRECTIVE_LENGTH - 2
        assert txs[0].date == datetime.date(2063, 1, 3)
        assert txs[-1].date == datetime.date(2063, 1, 6)

    def test_cutoff_none(self, input_filepath, existing_entries):
        """No culling."""
        txs = Importer(self.ACCOUNT_MAP, Extractors()).extract(
            input_filepath,
            existing_entries,
        )
        assert len(txs) == self.FULL_IMPORT_DIRECTIVE_LENGTH

    def test_no_existing_txs(self, input_filepath):
        """No existing txs -> no culling."""
        txs = Importer(self.ACCOUNT_MAP, Extractors(), cutoff_days=1).extract(
            input_filepath,
            [],
        )
        assert len(txs) == self.FULL_IMPORT_DIRECTIVE_LENGTH
        assert txs[0].date == datetime.date(2063, 1, 1)
        assert txs[-1].date == datetime.date(2063, 1, 6)

    def test_existing_txs_have_different_accounts(
        self,
        input_filepath,
        existing_entries,
    ):
        """Same as test_cutoff_nonzero, but the existing set contains txs for multiple accounts."""
        existing_entries[2] = Tx(datetime.date(2063, 1, 2), 'stick horse', flag='*',postings=[Post('Assets:SFB:Secret', amount='-300.00')])  # fmt: skip
        txs = Importer(self.ACCOUNT_MAP, Extractors(), cutoff_days=1).extract(input_filepath, existing_entries)  # fmt: skip
        assert len(txs) == self.FULL_IMPORT_DIRECTIVE_LENGTH - 1
        assert txs[0].date == datetime.date(2063, 1, 2)
        assert txs[-1].date == datetime.date(2063, 1, 6)
