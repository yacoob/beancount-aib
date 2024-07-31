"""Tests for specific extractors configured for AIB."""

import datetime
from copy import deepcopy

import pytest
from beancount.core.data import Transaction

from beancount_aib.extractors import AIB_EXTRACTORS
from beancount_tx_cleanup.cleaner import TxnPayeeCleanup
from beancount_tx_cleanup.cleaner_test import make_test_transaction_factory

TESTDATE = datetime.date(2510, 7, 9)
TTx = make_test_transaction_factory(TESTDATE)

# TODO: add more of these once AIB_EXTRACTORS is cleaned of stale rules
CLEANER_SCENARIOS: list[tuple[Transaction, Transaction]] = [
    (TTx('MUNDANE LTD'), TTx('MUNDANE LTD')),
    (TTx('BULLET*STAR'), TTx('BULLET*STAR')),
    (TTx('*MOBI ANGRY LEMON'), TTx('ANGRY LEMON', tags={'app'})),
    (TTx('VDC-INSOMNIA'), TTx('INSOMNIA', tags={'contactless'})),
    (TTx('VDP-TESCO'), TTx('TESCO', tags={'point-of-sale'})),
    (TTx('LEEROY JENKINS IE10293482'), TTx('LEEROY JENKINS', meta={'id': 'IE10293482'})),
    (TTx('VDP-PAYPAL *EVIL'), TTx('EVIL', tags={'point-of-sale'}, meta={'payment-processor': 'paypal'})),
    (TTx('VDC-SUMUP PASTRY'), TTx('PASTRY', tags={'contactless'}, meta={'payment-processor': 'sumup'})),
    (TTx('VDA-PERNAMBUCO 100.00 BRL@ 0.17'), TTx('PERNAMBUCO', tags={'atm', 'BRL'}, meta={'foreign-amount': '100.00'})),
    (TTx('VDC-DUNNES DOGHN'), TTx('Dunnes', tags={'contactless'}, meta={'location': 'doghn'})),
    (TTx('AMAZON.CO.UK Tasty Cake'), TTx('Amazon.co.uk Tasty Cake')),
]  # fmt: skip


@pytest.mark.parametrize(('in_tx', 'out_tx'), CLEANER_SCENARIOS)
class TestAibTxnCleanup:
    """Basic tests for the AIB_EXTRACTORS."""

    def test_payee_mangling(self, in_tx, out_tx):
        """Test different scenarios of payee cleanup.

        NOTE: you need a full regression test in addition to CLEANER_SCENARIOS above.
        """
        assert out_tx == TxnPayeeCleanup(in_tx, deepcopy(AIB_EXTRACTORS))
