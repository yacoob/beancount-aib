"""Extractors for AIB transactions."""

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


_e += E('Remove leading and trailing stars.', r'(^\*|\*$)', C)
_e += E('Remove stars next to a space.', r'( \*|\* )', P(' '))

_e += E(
    'Extract transaction time.',
    r'(?i)(time)? *(\d\d:\d\d)$',
    [M('time', v=r'\2'), C],
)

_e += E(
    'Handle non-Euro transactions.',
    r' ([\d.]+) ([A-Z]{3})@ [\d.]+',
    [M('foreign-amount'), T(r'\2'), C],
)

M_ID = M('id')
_e += [
    E('Extract transfer ID.', r' *(IE\d+)', [M_ID, C]),
    E(
        'Extract Ryanair transaction ID.',
        r'RYANAIR +(.+)',
        [M_ID, P('Ryanair')],
    ),
    E(
        'Extract FreeNow transaction ID.',
        r'FREENOW\*(?=.*\d)([A-Z\d-]+)',
        [M_ID, P('FreeNow')],
    ),
]

_e += E(
    'Determine transaction type - https://aib.ie/our-products/current-accounts/keeping-track-of-your-transactions',
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

TAG = 'payment-processor'
_e += E(
    'Extract payment processor company.',
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
    'Mark Google transactions 1/2',
    r'(?i)^google +\b(?!google|cloud|commerce|domain|ireland|music|payment|play|servic|svcs|store|youtub|voic)(.+)',
    [
        M_GOOG,
        P(r'\1'),
    ],
)
_e += E(
    'Mark Google transactions 2/2',
    r'(?i)^google +\b(payment|play|servic)',
    [M_GOOG, P(r'\g<0>')],
)

_e += E(
    'Remove the date strings on non-fee transactions.',
    r'(?<!TO )\d\d[A-Z]{3}\d\d *',
    C,
)


# behold the museum of Amazon payment strings >_<;
_e += [
    E(
        'Amazon transactions 1/4.',
        r'(?i)^(www.)?amazon((\.co)?\.[a-z]{2,3})(.*)',
        P(lambda m: r'Amazon' + m.group(2).lower() + m.group(4)),
    ),
    E(
        'Amazon transactions 1/4.',
        r'(?i)^amazon prime.*',
        P('Amazon Prime'),
    ),
    E(
        'Amazon transactions 1/4.',
        r'(?i)^amazon [\d-]+',
        P('Amazon'),
    ),
    E(
        'Amazon transactions 1/4.',
        r'(?i)^(amazon[^*]+)\*.*',
        P(r'\g<1>'),
    ),
]

SHORT_NAME_LENGTH = 3
_e += E(
    'Handle branch/location information.',
    r'(?i)^(applegreen|boi|burger king|camile thai|centra|circle k|dunnes|eurospar|gamestop|mace|mcdonalds|michie sushi|pablo picante|park rite|penneys|pizza hut|polonez|spar|starbucks|supervalu|topaz|ubl|ulster bank|wh smith|zabka) +(.+)$',
    [
        M('location', v=r'\2', transformer=lambda s: s.lower()),
        P(
            lambda m: m.group(1).upper()
            if len(m.group(1)) <= SHORT_NAME_LENGTH
            else m.group(1).capitalize(),
        ),
    ],
)
