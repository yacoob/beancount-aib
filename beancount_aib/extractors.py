"""Extractors for AIB transactions."""

from beancount_tx_cleanup.cleaner import (
    CLEANUP,
    TAG_DESTINATION,
    OldE,
    OldExtractors,
)

AIB_EXTRACTORS: OldExtractors = {
    # transaction timestamp
    'time': (OldE(r'(?i)(time)? *(\d\d:\d\d)$', value=r'\g<2>'),),
    # amount of foreign currency
    'foreign-amount': (OldE(r' ([\d.]+) [A-Z]{3}@ [\d.]+', replacement=r'\g<0>'),),
    # IDs that change for every instance of similar transactions
    'id': (
        OldE(r' *(IE\d+)'),
        OldE(r'RYANAIR +(.+)', replacement='Ryanair', value=r'\g<1>'),
        OldE(r'FREENOW\*(?=.*\d)([A-Z\d-]+)', replacement='FreeNow', value=r'\g<1>'),
    ),
    TAG_DESTINATION: (
        # foreign currency symbol
        OldE(r' [\d.]+ ([A-Z]{3})@ [\d.]+'),
        # transaction flavour
        # https://aib.ie/our-products/current-accounts/keeping-track-of-your-transactions
        OldE(r'(?i)^(vd[apc]|op/|atm|pos|mobi|inet|d/d|atmldg|ms[ap]|)[- ]',
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
          }),
    ),
    # payment processing companies
    'payment-processor': (
        OldE(r'(?i)^(paypal|sumup|sq|sp|zettle)[ _]', transformer=lambda m: m.lower(),
          translation={
            'sq': 'square',
            'sp': 'stripe',
          }),
        OldE(r'(?i)^google +\b(?!google|cloud|commerce|domain|ireland|music|payment|play|servic|svcs|store|youtub|voic)(.+)',
          replacement=r'\g<1>', value='google'),
        OldE(r'(?i)^google +\b(payment|play|servic)', replacement=r'\g<0>', value='google'),
    ),
    CLEANUP: (
        # remove the date strings, unless it's describing a quarterly fee transaction
        OldE(r'(?<!TO )\d\d[A-Z]{3}\d\d *'),
        # behold the museum of Amazon payment strings >_<;
        OldE(r'(?i)^(www.)?amazon((\.co)?\.[a-z]{2,3})(.*)', replacement=lambda m: r'Amazon' + m.group(2).lower() + m.group(4)),
        OldE(r'(?i)^amazon prime.*', replacement='Amazon Prime'),
        OldE(r'(?i)^amazon [\d-]+', replacement=r'Amazon'),
        OldE(r'(?i)^(amazon[^*]+)\*.*', replacement=r'\g<1>'),
    ),
    'location': (
        # An assortment of payees that routinely have a branch name present
        OldE('(?i)^(applegreen|boi|centra|circle k|dunnes|eurospar|gamestop|mcdonalds|michie sushi|pablo picante|park rite|penneys|pizza hut|polonez|spar|starbucks|supervalu|topaz|ubl|ulster bank|wh smith|zabka) +(.+)$',
          replacement=lambda m: m.group(1).upper() if len(m.group(1)) <= 3 else m.group(1).capitalize(),  # noqa: PLR2004
          value=r'\g<2>', transformer=lambda s: s.lower()),
    ),
}  # fmt: skip
