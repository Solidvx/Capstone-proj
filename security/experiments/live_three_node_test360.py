"""Run a test campaign of 30 trials for each configuration/attack (360 total).

Use from the repository root on the attacker Pi:
python -m security.experiments.live_three_node_test360 --help

Shares capture, validation, cleanup and evidence handling with live_three_node.
The official runner remains fixed at 100 trials per configuration/attack.
"""
from security.experiments.live_three_node import main as campaign_main


def main(argv=None):
    return campaign_main(argv, test360=True)


if __name__ == '__main__':
    raise SystemExit(main())
