"""Tests for specific extractors configured for AIB."""

import pytest
from beancount_aib.extractors import AIB_EXTRACTORS
from beancount_aib.helpers import Tx
from beancount_tx_cleanup.cleaner import TxnPayeeCleanup
from beancount_tx_cleanup.cleaner_test import CS, BasicExtractorTest

# TODO: add more of these once AIB_EXTRACTORS is cleaned of stale rules
CLEANER_SCENARIOS = [
    CS('MUNDANE LTD', 'MUNDANE LTD'),
    CS('BULLET*STAR', 'BULLET*STAR'),
    CS('*MOBI ANGRY LEMON', 'ANGRY LEMON', tags={'app'}),
    CS('VDC-INSOMNIA', 'INSOMNIA', tags={'contactless'}),
    CS('VDP-TESCO', 'TESCO', tags={'point-of-sale'}),
    CS('LEEROY JENKINS IE10293482', 'LEEROY JENKINS', meta={'id': 'IE10293482'}),
    CS('VDP-PAYPAL *EVIL', 'EVIL', tags={'point-of-sale'}, meta={'payment-processor': 'paypal'}),
    CS('VDC-SUMUP PASTRY', 'PASTRY', tags={'contactless'}, meta={'payment-processor': 'sumup'}),
    CS('VDA-PERNAMBUCO 100.00 BRL@ 0.17', 'PERNAMBUCO', tags={'atm', 'BRL'}, meta={'foreign-amount': '100.00'}),
]  # fmt: skip


@pytest.mark.parametrize('scenario', CLEANER_SCENARIOS)
class TestAibTxnCleanup(BasicExtractorTest):  # noqa: D101
    def test_payee_mangling(self, scenario):
        """Test different scenarios of payee cleanup.

        NOTE: you need a full regression test in addition to CLEANER_SCENARIOS above.
        """
        tx = Tx(self.date, scenario.input)
        clean_tx = Tx(
            self.date,
            scenario.payee,
            tags=scenario.tags,
            meta=scenario.meta,
        )
        assert clean_tx == TxnPayeeCleanup(tx, AIB_EXTRACTORS, preserveOriginalIn=None)
