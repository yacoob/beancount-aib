"""Extractors for AIB transactions."""
# ruff: noqa: ERA001
# pyright: reportArgumentType=false

from beancount_tx_cleanup.cleaner import (
    C,
    E,
    Extractors,
    M,
    P,
    T,
)

_e = Extractors()
AIB_EXTRACTORS = _e


# remove leading and trailing stars
_e += E(r'(^\*|\*$)', C)
_e += E(r'( \*|\* )', P(' '))


# transaction timestamp
_e += E(r'(?i)(time)? *(\d\d:\d\d)$', [M('time', v=r'\2'), C])


# foreign currency transaction
_e += E(r' ([\d.]+) ([A-Z]{3})@ [\d.]+', [M('foreign-amount'), T(r'\2'), C])


# IDs that change for every instance of similar transactions
M_ID = M('id')
_e += [
    E(r' *(IE\d+)', [M_ID, C]),
    E(r'RYANAIR +(.+)', [M_ID, P('Ryanair')]),
    E(r'FREENOW\*(?=.*\d)([A-Z\d-]+)', [M_ID, P('FreeNow')]),
]


# transaction flavour: https://aib.ie/our-products/current-accounts/keeping-track-of-your-transactions
_e += E(
    r'(?i)^(vd[apc]|op/|atm|pos|mobi|inet|d/d|atmldg|ms[ap]|)[- ]',
    [
        T(
            r'\1',
            translation={
                'atm': 'atm-aib',
                'atmldg': 'atm-lodgement',
                'd/d': 'direct-debit',
                'inet': 'online-interface',
                'mobi': 'app',
                'msa': 'atm',
                'msp': 'point-of-sale',
                'op/': 'direct-debit',
                'pos': 'point-of-sale',
                'vda': 'atm',
                'vdc': 'contactless',
                'vdp': 'point-of-sale',
            },
        ),
        C,
    ],
)


# payment processing companies
TAG = 'payment-processor'
_e += E(
    r'(?i)^(paypal|sumup|sq|sp|zettle)[ _]',
    [
        M(
            TAG,
            transformer=lambda m: m.lower(),
            translation={'sq': 'square', 'sp': 'stripe'},
        ),
        C,
    ],
)
M_GOOG = M(TAG, v='google')
_e += E(
    r'(?i)^google +\b(?!google|cloud|commerce|domain|ireland|music|payment|play|servic|svcs|store|youtub|voic)(.+)',
    [
        M_GOOG,
        P(r'\1'),
    ],
)
_e += E(r'(?i)^google +\b(payment|play|servic)', [M_GOOG, P(r'\g<0>')])


# remove the date strings, unless it's a part of a quarterly fee transaction
_e += E(r'(?<!TO )\d\d[A-Z]{3}\d\d *', C)


# behold the museum of Amazon payment strings >_<;
_e += [
    E(
        r'(?i)^(www.)?amazon((\.co)?\.[a-z]{2,3})(.*)',
        P(lambda m: r'Amazon' + m.group(2).lower() + m.group(4)),
    ),
    E(r'(?i)^amazon prime.*', P('Amazon Prime')),
    E(r'(?i)^amazon [\d-]+', P('Amazon')),
    E(r'(?i)^(amazon[^*]+)\*.*', P(r'\g<1>')),
]


# An assortment of payees that routinely have a branch name present
SHORT_NAME_LENGTH = 3
_e += E(
    r'(?i)^(applegreen|boi|centra|circle k|dunnes|eurospar|gamestop|mcdonalds|michie sushi|pablo picante|park rite|penneys|pizza hut|polonez|spar|starbucks|supervalu|topaz|ubl|ulster bank|wh smith|zabka) +(.+)$',
    [
        M('location', v=r'\2', transformer=lambda s: s.lower()),
        P(
            lambda m: m.group(1).upper()
            if len(m.group(1)) <= SHORT_NAME_LENGTH
            else m.group(1).capitalize(),
        ),
    ],
)
