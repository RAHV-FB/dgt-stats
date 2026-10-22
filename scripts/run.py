"""Build the project: every stage of every section, or the ones named.

Usage:
    python scripts/run.py --list                       # the stages in order, and what each writes
    python scripts/run.py all                          # everything (about two hours)
    python scripts/run.py national                     # one section's stages, in order
    python scripts/run.py national.ingest --force      # one stage
    python scripts/run.py regional.build models.features   # several, in the order given

The sections are national, regional, drivers, models, sources, charts and site; the stages and
what each reads and writes are declared in ``src/dgt_stats/pipeline.py``. ``--force`` rebuilds
data layers that already exist (national.ingest, national.process, regional.build), and
``--years`` limits national.ingest to some years of the crash microdata.
"""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from dgt_stats import pipeline  # noqa: E402

log = logging.getLogger("run")
THREAD_VARIABLES = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")


def list_stages() -> None:
    width = max(len(stage.key) for stage in pipeline.STAGES)
    print(f"{'stage':<{width}}  {'min':>4}  what it does -> what it writes")
    for stage in pipeline.STAGES:
        note = "" if stage.in_all else "  (run by name only)"
        print(f"{stage.key:<{width}}  {stage.minutes:>4g}  {stage.does}{note}")
        print(f"{'':<{width}}        -> {stage.writes}")


def run_in_process(key: str, force: bool, years: list[int] | None) -> None:
    stage = pipeline.BY_KEY[key]
    kwargs: dict = {}
    if stage.takes_force:
        kwargs["force"] = force
    if stage.takes_years and years:
        kwargs["years"] = tuple(years)
    stage.function()(**kwargs)


def run_in_child(stage: pipeline.Stage, args: argparse.Namespace) -> int:
    """One stage in a fresh process, with one BLAS thread where the stage needs it."""
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(filter(None, (str(SRC), env.get("PYTHONPATH"))))
    if stage.single_thread:
        env.update({variable: "1" for variable in THREAD_VARIABLES})
    command = [sys.executable, __file__, "--in-process", stage.key]
    if args.force:
        command.append("--force")
    if args.years:
        command += ["--years", *map(str, args.years)]
    if args.verbose:
        command.append("-v")
    return subprocess.run(command, env=env).returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("targets", nargs="*", help="all, a section, or section.stage")
    parser.add_argument("--list", action="store_true", help="list the stages and exit")
    parser.add_argument("--force", action="store_true", help="rebuild data layers that exist")
    parser.add_argument("--years", type=int, nargs="+", help="national.ingest: microdata years")
    parser.add_argument("-v", "--verbose", action="store_true", help="debug-level logging")
    parser.add_argument("--in-process", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )
    if args.list or not args.targets:
        list_stages()
        return 0
    if args.in_process:
        (key,) = args.targets
        run_in_process(key, args.force, args.years)
        return 0
    stages = pipeline.select(args.targets)
    started = time.perf_counter()
    for stage in stages:
        log.info("--- %s: %s", stage.key, stage.does)
        stage_started = time.perf_counter()
        code = run_in_child(stage, args)
        if code:
            log.error("%s failed (exit %d); later stages not run", stage.key, code)
            return code
        log.info("--- %s done in %.0f s", stage.key, time.perf_counter() - stage_started)
    log.info("%d stages done in %.0f s", len(stages), time.perf_counter() - started)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
