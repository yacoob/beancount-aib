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

_exs: Extractors = []
AIB_EXTRACTORS = _exs

# remove leading and trailing stars
_exs.append(E(r=r'(^\*|\*$)', actions=[C]))
_exs.append(E(r=r'( \*|\* )', actions=[P(v=' ')]))

# transaction timestamp
_exs.append(
    E(r=r'(?i)(time)? *(\d\d:\d\d)$', actions=[M(n='time', v=r'\2'), C]),
)

# foreign currency transaction
_exs.append(
    E(
        r=r' ([\d.]+) ([A-Z]{3})@ [\d.]+',
        actions=[M(n='foreign-amount'), T(v=r'\2'), C],
    ),
)

# IDs that change for every instance of similar transactions
M_ID = M(n='id')
_exs.append(E(r=r' *(IE\d+)', actions=[M_ID, C]))
_exs.append(E(r=r'RYANAIR +(.+)', actions=[M_ID, P(v='Ryanair')]))
_exs.append(
    E(r=r'FREENOW\*(?=.*\d)([A-Z\d-]+)', actions=[M_ID, P(v='FreeNow')]),
)

# transaction flavour
# https://aib.ie/our-products/current-accounts/keeping-track-of-your-transactions
_exs.append(
    E(
        r=r'(?i)^(vd[apc]|op/|atm|pos|mobi|inet|d/d|atmldg|ms[ap]|)[- ]',
        actions=[
            T(
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
    ),
)

# payment processing companies
TAG = 'payment-processor'
_exs.append(
    E(
        r=r'(?i)^(paypal|sumup|sq|sp|zettle)[ _]',
        actions=[
            M(
                n=TAG,
                transformer=lambda m: m.lower(),
                translation={
                    'sq': 'square',
                    'sp': 'stripe',
                },
            ),
            C,
        ],
    ),
)
M_GOOG = M(n=TAG, v='google')
_exs.append(
    E(
        r=r'(?i)^google +\b(?!google|cloud|commerce|domain|ireland|music|payment|play|servic|svcs|store|youtub|voic)(.+)',
        actions=[
            M_GOOG,
            P(v=r'\1'),
        ],
    ),
)
_exs.append(
    E(
        r=r'(?i)^google +\b(payment|play|servic)',
        actions=[M_GOOG, P(v=r'\g<0>')],
    ),
)

# remove the date strings, unless it's describing a quarterly fee transaction
_exs.append(E(r=r'(?<!TO )\d\d[A-Z]{3}\d\d *', actions=[C]))


# behold the museum of Amazon payment strings >_<;
_exs.append(
    E(
        r=r'(?i)^(www.)?amazon((\.co)?\.[a-z]{2,3})(.*)',
        actions=[P(v=lambda m: r'Amazon' + m.group(2).lower() + m.group(4))],
    ),
)
_exs.append(E(r=r'(?i)^amazon prime.*', actions=[P(v='Amazon Prime')]))
_exs.append(E(r=r'(?i)^amazon [\d-]+', actions=[P(v='Amazon')]))
_exs.append(E(r=r'(?i)^(amazon[^*]+)\*.*', actions=[P(v=r'\g<1>')]))

# An assortment of payees that routinely have a branch name present
SHORT_NAME_LENGTH = 3
_exs.append(
    E(
        r='(?i)^(applegreen|boi|centra|circle k|dunnes|eurospar|gamestop|mcdonalds|michie sushi|pablo picante|park rite|penneys|pizza hut|polonez|spar|starbucks|supervalu|topaz|ubl|ulster bank|wh smith|zabka) +(.+)$',
        actions=[
            M(n='location', v=r'\2', transformer=lambda s: s.lower()),
            P(
                v=lambda m: m.group(1).upper()
                if len(m.group(1)) <= SHORT_NAME_LENGTH
                else m.group(1).capitalize(),
            ),
        ],
    ),
)
