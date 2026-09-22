# Notebooks

None were written, and none are planned. An early plan listed ten explanatory notebooks, one per
research question. By the time the results existed, three things had taken their place:

- the scripts in `scripts/` run the whole pipeline from the raw files to the site, each step
  idempotent and logged;
- the tests in `tests/` hold the reconciliation checks and the synthetic recoveries a notebook
  would have shown by hand;
- the site's own pages carry the explanation beside each table and figure, with the limits stated
  where the result is.

A notebook that repeated any of these would be a second copy to keep in step. If one is ever
wanted, the rule stands: reusable transformations, metrics, models and plotting functions live in
`src/dgt_stats/`, and a notebook only calls them and explains.
