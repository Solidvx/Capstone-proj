"""N06 원수/미정의 지표와 두 기존 점수 경계의 회귀."""
import json
import math
import random
import unittest
from unittest.mock import patch

from security.experiments import run_eval
from security.experiments.analyze_roc import metrics
from security.experiments.run_eval import format_metric
from security.ids.rule_baseline import confusion_metrics, metrics_at, roc_auc


class EvaluationMetricsTests(unittest.TestCase):
    def test_independent_mixed_counts_and_ratios(self):
        result = confusion_metrics(2, 1, 3, 4)
        expected = {
            'tp': 2, 'fp': 1, 'tn': 3, 'fn': 4,
            'precision': 2 / 3, 'recall': 1 / 3,
            'fpr': 1 / 4, 'fnr': 2 / 3, 'tnr': 3 / 4,
            'f1': 4 / 9, 'balanced_accuracy': 13 / 24,
            'mcc': 2 / math.sqrt(504),
        }
        self.assertEqual(set(result), set(expected))
        for key, value in expected.items():
            self.assertAlmostEqual(result[key], value, msg=key)

    def test_empty_and_single_class_are_not_zero_percent_success(self):
        for counts, undefined in (
            ((0, 0, 0, 0), ('precision', 'recall', 'fpr', 'fnr', 'tnr', 'f1', 'balanced_accuracy', 'mcc')),
            ((0, 0, 2, 0), ('precision', 'recall', 'fnr', 'f1', 'balanced_accuracy', 'mcc')),
            ((2, 0, 0, 0), ('fpr', 'tnr', 'balanced_accuracy', 'mcc')),
            ((0, 1, 0, 0), ('recall', 'fnr', 'balanced_accuracy', 'mcc')),
        ):
            with self.subTest(counts=counts):
                result = confusion_metrics(*counts)
                for name in undefined:
                    self.assertIsNone(result[name], name)
                json.dumps(result, allow_nan=False)
        # With actual positives or FP present F1=0 is defined; this is not N/A.
        self.assertEqual(confusion_metrics(0, 0, 2, 3)['f1'], 0)
        self.assertEqual(confusion_metrics(0, 1, 0, 0)['f1'], 0)

    def test_all_wrong_predictions_keep_negative_mcc(self):
        result = confusion_metrics(0, 2, 0, 3)
        self.assertEqual(result['mcc'], -1)
        self.assertEqual(result['balanced_accuracy'], 0)
        self.assertEqual(result['fnr'], 1)
        self.assertEqual(result['fpr'], 1)

    def test_bad_confusion_counts_are_refused(self):
        for value in (-1, True, 1.0, '1', None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                confusion_metrics(value, 0, 0, 0)

    def test_same_windows_have_same_counts_in_both_existing_aggregators(self):
        labels = [1, 1, 0, 0, 0, 0, 1, 1, 1, 1]
        types = ['fuzzy', 'spoofing', '', '', '', '', 'replay', 'replay', 'replay', 'fuzzy']
        scores = [1, 1, 1, 0, 0, 0, 0, 0, 0, 0]
        rows = [dict(score=s, label=y, attack_type=a) for s, y, a in zip(scores, labels, types)]
        baseline = metrics_at(iter(scores), iter(labels), iter(types), .5)
        window_roc = metrics(rows, .5)
        for key, value in confusion_metrics(2, 1, 3, 4).items():
            self.assertEqual(baseline[key], value)
            self.assertEqual(window_roc[key], value)
        self.assertEqual(baseline['metric_unit'], 'ratio')
        self.assertEqual(window_roc['metric_unit'], 'ratio')
        self.assertEqual(baseline['normal_windows'], 4)
        self.assertEqual(baseline['attack_windows'], 6)
        self.assertEqual(baseline['per_attack_counts']['fuzzy'], {'detected': 1, 'windows': 2})
        self.assertEqual(baseline['per_attack']['fuzzy'], .5)
        self.assertNotIn('flooding', baseline['per_attack'])  # absent is not zero detection

    def test_existing_distinct_threshold_boundaries_are_preserved(self):
        baseline = metrics_at([0, 0], [0, 1], ['', 'fuzzy'], 0)
        window_roc = metrics([dict(score=0, label=0, attack_type=''),
                              dict(score=0, label=1, attack_type='fuzzy')], 0)
        self.assertEqual((baseline['tp'], baseline['fp']), (1, 1))
        self.assertEqual((window_roc['tp'], window_roc['fp']), (0, 0))
        self.assertEqual(baseline['decision'], 'score >= threshold')
        self.assertEqual(window_roc['decision'], 'score > threshold')

    def test_mismatched_lengths_and_ground_truth_are_refused(self):
        for args in (([1], [], [], .5), ([1], [1], [], .5),
                     ([1], [1], ['fuzzy', 'replay'], .5),
                     ([1], [1], [''], .5), ([1], [0], ['fuzzy'], .5),
                     ([1], [1], [None], .5)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                metrics_at(*args)
        for label in (True, 1.0, 2, -1, '1', None):
            with self.subTest(label=label), self.assertRaises(ValueError):
                metrics_at([1], [label], ['fuzzy'], .5)

    def test_nonfinite_and_nonnumeric_scores_thresholds_are_refused(self):
        for value in (float('nan'), float('inf'), -float('inf'), True, '1', None):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    metrics_at([value], [1], ['fuzzy'], .5)
                with self.assertRaises(ValueError):
                    metrics_at([1], [1], ['fuzzy'], value)
                with self.assertRaises(ValueError):
                    roc_auc([value], [1])
        with self.assertRaises(ValueError):
            roc_auc([1], [])

    def test_auc_ties_order_empty_and_one_class(self):
        self.assertEqual(roc_auc([0, 1], [0, 1]), 1)
        self.assertEqual(roc_auc([1, 0], [0, 1]), 0)
        self.assertEqual(roc_auc([1, 1], [0, 1]), .5)
        self.assertEqual(roc_auc([1, 1], [1, 0]), .5)
        for scores, labels in (([], []), ([1], [1]), ([0], [0])):
            self.assertIsNone(roc_auc(scores, labels))
        json.dumps({'auc': roc_auc([], []), **metrics_at([], [], [], 0)}, allow_nan=False)

    def test_legacy_masquerade_type_and_na_display(self):
        result = metrics_at([1], [1], ['masquerade'], 1)
        self.assertEqual(result['per_attack']['masquerade'], 1)
        self.assertIsNone(result['fpr'])
        self.assertEqual(format_metric(None), 'N/A')
        self.assertEqual(format_metric(None, '5.1%'), 'N/A')
        self.assertEqual(format_metric(0), '0.000')
        self.assertEqual(format_metric(.25, '.1%'), '25.0%')

    def test_evaluation_scores_and_labels_cannot_select_the_threshold(self):
        original_builder = run_eval.build_dataset
        original = run_eval.prepare_rule_evaluation(random.Random(42))
        def changed_evaluation(rng):
            train, test = original_builder(rng)
            changed = [([x + 1e9 for x in vector], 0, '') for vector, _, _ in test]
            return train, changed
        with patch.object(run_eval, 'build_dataset', side_effect=changed_evaluation):
            changed = run_eval.prepare_rule_evaluation(random.Random(42))
        self.assertNotEqual(original[3], changed[3])
        self.assertEqual(original[1], changed[1])
        self.assertEqual(original[2], changed[2])
        self.assertEqual(original[4], changed[4])
        self.assertEqual(len(original[2]), 60)
        normal_evaluation_scores = [original[0].score(v) for v, y, _ in original[3] if y == 0]
        old_leaking_threshold = run_eval._percentile(normal_evaluation_scores, .99)
        self.assertNotEqual(original[4], old_leaking_threshold)

    def test_separate_synthetic_draws_preserve_original_train_and_evaluation(self):
        original_train, original_test = run_eval.build_dataset(random.Random(43))
        _, train, calibration, test, _ = run_eval.prepare_rule_evaluation(random.Random(43))
        self.assertEqual(train, original_train)
        self.assertEqual(test, original_test)
        self.assertEqual(len(calibration), 60)
        self.assertNotEqual(calibration, [v for v, y, _ in test if y == 0])
        repeated = run_eval.prepare_rule_evaluation(random.Random(43))
        self.assertEqual((calibration, test), (repeated[2], repeated[3]))

    def test_missing_or_invalid_calibration_refuses_invented_threshold(self):
        for values, q in (([], .99), ([float('nan')], .99), ([True], .99),
                          ([1], -1), ([1], 1.1), ([1], float('nan'))):
            with self.subTest(values=values, q=q), self.assertRaises(ValueError):
                run_eval._percentile(values, q)
        with patch.object(run_eval, 'CALIBRATION_S', 0), self.assertRaises(ValueError):
            run_eval.prepare_rule_evaluation(random.Random(42))


if __name__ == '__main__':
    unittest.main()
