"""Crash-severity models and their tests outside the data they were fitted on.

The models are trained on the regional crash records (:mod:`dgt_stats.regional`); DGT's national
records and Barcelona's serve only as test domains, and no record is ever moved between sources.

``ml``              feature catalogue and tables, the source models, their rule baselines, the
                    recording checks, and the result tables, cards and leakage audit
``validation``      harmonisation across sources, transfer tests, the Barcelona diagnosis, the DGT
                    microdata audit, generalisability and the model decisions
``review``          the independent re-evaluation of every model
``severity_model``  the published crash-severity calculator's model (Catalonia)
"""
