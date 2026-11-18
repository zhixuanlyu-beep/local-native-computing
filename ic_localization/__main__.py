"""python -m ic_localization --report PATH --trace PATH"""
import argparse
from .report import generate, verify


def main():
    parser = argparse.ArgumentParser(description="M7 exhaustive chain-localization optimizer")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--report")
    mode.add_argument("--verify-report")
    parser.add_argument("--trace", required=True)
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    if args.workers < 1:
        parser.error("--workers must be positive")
    action, path = (verify, args.verify_report) if args.verify_report else (generate, args.report)
    report = action(path, args.trace, workers=args.workers)
    print(report["implementation_status"], report["fifo_candidate_input_checks"], "FIFO checks", flush=True)
    if report["implementation_status"] != "accepted":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
