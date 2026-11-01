"""Train the model.   python -m app.train            (real data in data/cardekho.csv)
                      python -m app.train --demo     (made-up demo data, to try the interface)"""
import argparse
import os
import sys

import pandas as pd

from .data import clean_data
from .modeling import BASELINE, save_artifact, train_model
from .synthetic import make_synthetic_cars

HELP_DATA = """Could not find {path}.

1. Create a free account at kaggle.com and search for "Vehicle dataset from CarDekho".
2. Download "CAR DETAILS FROM CAR DEKHO.csv".
3. Save it as {path} (rename it to cardekho.csv).
Or run with --demo to try the app on made-up data first."""


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data", default="data/cardekho.csv")
    p.add_argument("--out", default="models")
    p.add_argument("--demo", action="store_true", help="train on made-up data (not real prices)")
    p.add_argument("--quick", action="store_true", help="smaller models, for tests")
    args = p.parse_args(argv)

    if args.demo:
        raw, source = make_synthetic_cars(), "synthetic demo data"
    elif not os.path.exists(args.data):
        print(HELP_DATA.format(path=args.data))
        return 1
    else:
        raw, source = pd.read_csv(args.data), os.path.basename(args.data)

    df, report = clean_data(raw)
    print(f"Rows in: {report['rows_in']}  | dropped: {report['dropped_missing']} missing, "
          f"{report['dropped_duplicates']} duplicates, {report['dropped_implausible']} implausible  | kept: {report['rows_out']}")
    print("Training and comparing models (this can take a minute)...")
    artifact = train_model(df, report, source, demo=args.demo, quick=args.quick)
    path = save_artifact(artifact, args.out)

    info = artifact["info"]
    print(f"\n{'model':38} {'typical error (CV)':>20} {'typical error (test)':>22}")
    for r in info["comparison"]:
        star = "  <- chosen" if r["model"] == info["model"] else ""
        print(f"{r['model']:38} {r['cv_mdape']:>19.1%} {r['test_mdape']:>21.1%}{star}")
    iv = info["interval"]
    print(f"\nThe {iv['level']:.0%} price range held for {iv['test_coverage']:.0%} of unseen test cars.")
    print(f"Saved {path}. Restart the server to load it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
