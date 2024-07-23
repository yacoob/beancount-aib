"""Tests for specific extractors configured for AIB."""

import datetime
from copy import deepcopy

import pytest
from beancount_aib.extractors import AIB_EXTRACTORS
from beancount_tx_cleanup.cleaner import OldTxnPayeeCleanup
from beancount_tx_cleanup.cleaner_test import CS
from beancount_tx_cleanup.helpers import Tx

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
class TestAibTxnCleanup:
    """Basic tests for the AIB_EXTRACTORS."""

    date = datetime.date(2510, 7, 9)

    # TODO: reuse the code from beancount_tx_cleanup.cleanup_test.TestCleanerFunctionality.test_cleaning
    #       or retire this entire class in favour of a completeness check in the regression test.
    def test_payee_mangling(self, scenario):
        """Test different scenarios of payee cleanup.

        NOTE: you need a full regression test in addition to CLEANER_SCENARIOS above.
        """
        extractors = deepcopy(AIB_EXTRACTORS)
        tx = Tx(
            self.date,
            scenario.input_payee,
            tags=scenario.input_tags,
            meta=scenario.input_meta,
        )
        clean_tx = Tx(
            self.date,
            scenario.payee,
            tags=scenario.tags,
            meta=scenario.meta,
        )
        assert clean_tx == OldTxnPayeeCleanup(
            tx,
            extractors,
            preserveOriginalIn=None,
        )
