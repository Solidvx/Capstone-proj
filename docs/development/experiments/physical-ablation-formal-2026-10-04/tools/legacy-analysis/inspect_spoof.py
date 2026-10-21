from pathlib import Path
p=next(Path('docs/development/experiments/physical-ablation-formal-2026-10-04/raw/ABLATION-FORMAL-C1-SPOOF-001/ivi').rglob('candump.log'))
s=p.read_text().splitlines();print('\n'.join(s[169175:169182]))
