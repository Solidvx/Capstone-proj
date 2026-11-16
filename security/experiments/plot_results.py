"""Headless plots of hash-validated ablation runs or explicitly sourced EKF CSV."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

from security.experiments.summarize_ablation import summarize


def ekf_data(csv_path, manifest_path):
    manifest = json.loads(manifest_path.read_text())
    if manifest.get('schema') != 'ekf-reference-v1' or manifest.get('environment') not in (
            'synthetic', 'vcan', 'physical-can'):
        raise ValueError('explicit EKF provenance required')
    if not isinstance(manifest.get('reference_source'), str) or not manifest['reference_source'].strip():
        raise ValueError('describe how reference SOC was obtained')
    if hashlib.sha256(csv_path.read_bytes()).hexdigest() != manifest.get('csv_sha256'):
        raise ValueError('EKF CSV hash mismatch')
    with csv_path.open(newline='') as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != ['time_s', 'reference_soc_pct', 'estimated_soc_pct']:
            raise ValueError('expected time_s,reference_soc_pct,estimated_soc_pct')
        rows = [tuple(float(row[name]) for name in reader.fieldnames) for row in reader]
    if len(rows) < 2 or any(not all(math.isfinite(v) for v in row) or row[0] < 0
                            or not all(0 <= v <= 100 for v in row[1:]) for row in rows):
        raise ValueError('at least two finite, in-range samples required')
    if any(b[0] <= a[0] for a, b in zip(rows, rows[1:])):
        raise ValueError('timestamps must strictly increase')
    errors = [estimated - reference for _, reference, estimated in rows]
    return rows, {**manifest, 'samples': len(rows),
                  'rmse_percentage_points': math.sqrt(sum(e * e for e in errors) / len(errors)),
                  'max_absolute_error_percentage_points': max(map(abs, errors)),
                  'official_acceptance': False,
                  'note': 'Sample-weighted error against declared reference; not proof of true battery SOC accuracy.'}


def render_ablation(result, plt, output):
    rows = result['summary']
    attacks = list(dict.fromkeys(row['attack_type'] for row in rows))
    labels = {1: 'Unprotected', 2: 'SecOC', 3: 'SecOC + IDS'}
    for field, title, unit in (
            ('attack_success_rate', 'Attack success', '% of valid trials'),
            ('detected_rate', 'IDS detection', '% of valid trials'),
            ('avg_detected_latency_s', 'Mean detection latency', 'seconds; detected trials only')):
        fig, ax = plt.subplots(figsize=(12, 6), layout='constrained')
        for config in (1, 2, 3):
            group = [next(r for r in rows if r['config'] == config and r['attack_type'] == a) for a in attacks]
            xs = [i + (config - 2) * .25 for i in range(len(attacks))]
            values = [r[field] if config == 3 or field == 'attack_success_rate' else None for r in group]
            scale = 1 if field.endswith('_s') else 100
            bars = ax.bar(xs, [math.nan if v is None else v * scale for v in values], .23, label=labels[config])
            for x, bar, value, row in zip(xs, bars, values, group):
                label = 'N/A' if value is None else (
                    f"{value:.4g}s; {row['detected_count']}/{row['valid_trials']} detected" if field.endswith('_s')
                    else f"n={row['valid_trials']}")
                ax.annotate(label, (x, 0 if value is None else bar.get_height()), xytext=(0, 4),
                            textcoords='offset points', ha='center', fontsize=7, rotation=30)
        ax.set_xticks(range(len(attacks)), attacks)
        ax.set_xlim(-.65, len(attacks) - .35)
        ax.set_ylabel(unit)
        largest = max((row[field] or 0 for row in rows), default=0)
        ax.set_ylim(0, max(.001, largest * 1.8) if field.endswith('_s') else 120)
        ax.set_title(f"{title} — {result['environment']}\nMatrix complete: {result['matrix_complete']}; official 1200 complete: {result['official_1200_complete']}")
        ax.legend(loc='upper right')
        ax.set_xlabel('N/A is not zero. Invalid/missing trials excluded; no security acceptance verdict.',
                      fontsize=8, labelpad=12)
        fig.savefig(output / (field + '.png'), dpi=140)
        plt.close(fig)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='kind', required=True)
    ablation = sub.add_parser('ablation')
    ablation.add_argument('--input-dir', type=Path, required=True)
    ekf = sub.add_parser('ekf')
    ekf.add_argument('--csv', type=Path, required=True)
    ekf.add_argument('--manifest', type=Path, required=True)
    for child in (ablation, ekf):
        child.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.kind == 'ablation':
            result = summarize(args.input_dir)
            result['source_manifest_sha256'] = hashlib.sha256((args.input_dir / 'manifest.json').read_bytes()).hexdigest()
        else:
            rows, result = ekf_data(args.csv, args.manifest)
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        args.output_dir.mkdir(parents=True, exist_ok=False)
        if args.kind == 'ablation':
            render_ablation(result, plt, args.output_dir)
        else:
            fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True, layout='constrained')
            times, reference, estimated = zip(*rows)
            axes[0].plot(times, reference, label='Declared reference')
            axes[0].plot(times, estimated, label='EKF estimate')
            axes[0].set_ylabel('SOC (%)')
            axes[0].legend()
            axes[0].set_title(f"EKF — {result['environment']} (not acceptance evidence)\nReference: {result['reference_source']}")
            axes[1].plot(times, [e-r for e, r in zip(estimated, reference)])
            axes[1].axhline(0, color='gray', linestyle='--')
            axes[1].set(xlabel='Time (s)', ylabel='Error (percentage points)',
                        title=f"RMSE {result['rmse_percentage_points']:.4f} pp; max |error| {result['max_absolute_error_percentage_points']:.4f} pp")
            fig.savefig(args.output_dir / 'ekf_error.png', dpi=140)
            plt.close(fig)
        (args.output_dir / 'summary.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps({'status': 'RENDERED', 'output': str(args.output_dir), 'official_acceptance': False}))
        return 0
    except (OSError, ValueError, KeyError, TypeError, ImportError) as error:
        print(json.dumps({'status': 'INVALID', 'reason': str(error)}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
