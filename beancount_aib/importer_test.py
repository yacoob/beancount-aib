"""Tests for the importer itself."""

import datetime
from io import StringIO
from typing import ClassVar

import pytest
from beancount_aib.helpers import Bal, Post, Tx
from beancount_aib.importer import Importer, LineNoDictReader


class StringMemo:
    """StringMemo is the equivalent of beancount.ingest.cache._FileMemo backed by a string, instead of a temporary file."""

    def __init__(self, contents: str):  # noqa: D107
        self.backing_string: str = contents
        self.name = '<string-backed file>'

    def mimetype(self):  # noqa: D102
        # this is a very rudimentary check, but it's sufficient for my usecase :P
        return 'text/csv' if ',' in self.backing_string else 'text/plain'

    def head(self, num_bytes=8192):  # noqa: D102
        return self.backing_string[:num_bytes]

    def contents(self):  # noqa: D102
        return self.backing_string


def test_StringMemo():  # noqa: D103
    c = '\n'.join(['looks,like,csv,file,no?', '1,2,3,4,5'])
    s = StringMemo(c)
    assert s.mimetype() == 'text/csv'
    assert s.head() == c
    assert s.contents() == c
    c = 'a ' * 4095 + 'b ' + 'b ' * 4096
    s = StringMemo(c)
    assert s.mimetype() == 'text/plain'
    assert s.head() == 'a ' * 4095 + 'b '
    assert s.contents() == c


@pytest.fixture()
def filecontents(request):
    """Provide the string from filecontents mark.

    Both leading and trailing whitespace are trimmed from the content
    """
    marker_content = None
    if marker := request.node.get_closest_marker('filecontents'):
        marker_content = marker.args[0]
    content = marker_content or ''
    return content.strip()


@pytest.fixture()
def input_file(filecontents):
    """Provide the filecontents mark as a standard file object."""
    return StringIO(filecontents)


@pytest.fixture()
def input_memo(filecontents):
    """Provide the filecontents mark as a FileMemo-like object, suitable to feed into a beancount Importer."""
    return StringMemo(filecontents)


@pytest.mark.filecontents("""
lead,support,support2,support3
Picard,Data,Worf,Troi
Mal,Zoe,Kaylee,Wash
Abed,Troy,Britta,Shirley
Bojack,Diane,Princess Carolyn,Todd
""")
def testLineNoDictReader(input_file):  # noqa: D103
    assert list(LineNoDictReader(input_file)) == [
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


class TestImporter:
    """Tests for the importer.

    Those tests focus on importer's functionality - eg. file recognition,
    parsing, etc. For full coverage, you need a beancount regression test with a recent data set.

    """

    account_map: ClassVar[dict[str, str]] = {'111': 'Assets:AIB:Secret'}
    importer = Importer(account_map, cutoff_days=None)

    @pytest.mark.filecontents("""
    absolutely: not a csv file
    more: 42
    """)
    def test_not_a_csv_file(self, input_memo):  # noqa: D102
        assert not self.importer.identify(input_memo)
        assert self.importer.file_date(input_memo) is None
        assert self.importer.file_account(input_memo) == self.importer.default_account
        assert self.importer.extract(input_memo, []) == []

    @pytest.mark.filecontents("""
    Posted Account, Posted Transactions Date, Description1
    "111", "01/01/2024", "nuts and bolts"
    "111", "02/01/2024", "croissants"
    "111", "03/01/2024", "twenty feet of pure white snow
    """)
    def test_valid_file(self, input_memo):  # noqa: D102
        assert self.importer.identify(input_memo)
        assert self.importer.file_date(input_memo) == datetime.date(2024, 1, 3)
        assert self.importer.file_account(input_memo) == self.account_map['111']

    @pytest.mark.filecontents("""
    111,x,y
    111,a,b
    111,c,d
    999,e,f
    111,g,h
    """)
    def test_multiple_accounts_file(self, input_memo):  # noqa: D102
        assert not self.importer.identify(input_memo)

    @pytest.mark.filecontents("""
    999,x,y
    999,a,b
    999,c,d
    999,e,f
    999,g,h
    """)
    def test_account_not_in_map(self, input_memo):  # noqa: D102
        assert not self.importer.identify(input_memo)


@pytest.mark.filecontents("""
Posted Account, Posted Transactions Date, Description1, Description2, Description3, Debit Amount, Credit Amount,Balance,Posted Currency,Transaction Type,Local Currency Amount,Local Currency
"111","01/01/2024","nine golden rings","","","9.99",,"1200.00",EUR,"Debit"," 9.99",EUR
"111","02/01/2024","ring wraith costume","","","200.00",,"1000.00",EUR,"Debit"," 200.00",EUR
"111","03/01/2024","stick horse","","","300.00",,"700.00",EUR,"Debit"," 300.00",EUR
"111","04/01/2024","ACME hobbit trap","","","50.00",,"650.00",EUR,"Debit"," 50.00",EUR
"111","05/01/2024","stick wyvern","","","400.00",,"250.00",EUR,"Debit"," 400.00",EUR
""")
class TestImporterCutoff:
    """These tests excercise culling in situations where the imported txs overlap with the existing ones.

    Beancount dedupes those further down the import pipeline, but that
    still leaves them visible in the fava import interface.

    All of the tests in TestImporterCutoff use the file content from
    the filecontents mark on the class itself.
    """

    account_name = 'Assets:AIB:Secret'
    account_map: ClassVar[dict[str, str]] = {'111': account_name}

    @pytest.fixture()
    def existing_entries(self):
        """Provide a set of existing txs. Modify as needed in each test."""
        return [
            Tx(datetime.date(2024, 1, 1), 'nine golden rings', postings=[Post(self.account_name, amount='9.99')]),
            Tx(datetime.date(2024, 1, 2), 'ring wraith costume', postings=[Post(self.account_name, amount='200.00')]),
            Tx(datetime.date(2024, 1, 3), 'stick horse', postings=[Post(self.account_name, amount='300.00')]),
            Bal(self.account_name, '700', datetime.date(2024, 1, 4)),
        ]  # fmt: skip

    def test_cutoff_zero(self, input_memo, existing_entries):
        """Remove txs older than the oldest existing tx for the account in question."""
        txs = Importer(self.account_map, cutoff_days=0).extract(input_memo, existing_entries)  # fmt: skip
        assert len(txs) == 4  # noqa: PLR2004
        assert txs[0].date == datetime.date(2024, 1, 3)
        assert txs[-1].date == datetime.date(2024, 1, 6)

    def test_no_existing_txs(self, input_memo):
        """No existing txs -> no culling."""
        txs = Importer(self.account_map, cutoff_days=1).extract(input_memo, [])
        assert len(txs) == 6  # noqa: PLR2004
        assert txs[0].date == datetime.date(2024, 1, 1)
        assert txs[-1].date == datetime.date(2024, 1, 6)

    def test_existing_txs_have_different_accounts(self, input_memo, existing_entries):
        """Same as test_cutoff_zero, but cutoff_days is greater, and the existing set contains txs for multiple accounts."""
        existing_entries[2] = Tx(datetime.date(2024, 1, 2), 'stick horse', postings=[Post('Assets:SFB:Secret', amount='300.00')])  # fmt: skip
        txs = Importer(self.account_map, cutoff_days=1).extract(input_memo, existing_entries)  # fmt: skip
        assert len(txs) == 6  # noqa: PLR2004
        assert txs[0].date == datetime.date(2024, 1, 1)
        assert txs[-1].date == datetime.date(2024, 1, 6)
