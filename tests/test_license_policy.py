import unittest

from ingest.birdtrainer.license_policy import evaluate_license


class LicensePolicyTests(unittest.TestCase):
    def test_cc_by_is_allowed_for_derivatives(self):
        decision = evaluate_license("CC BY 4.0", "https://creativecommons.org/licenses/by/4.0/", derivative_required=True)
        self.assertTrue(decision.allowed)
        self.assertTrue(decision.derivative_allowed)
        self.assertTrue(decision.commercial_allowed)

    def test_no_derivatives_is_rejected_for_clips(self):
        decision = evaluate_license("CC BY-ND 4.0", "https://creativecommons.org/licenses/by-nd/4.0/", derivative_required=True)
        self.assertFalse(decision.allowed)
        self.assertFalse(decision.derivative_allowed)

    def test_noncommercial_is_rejected_for_commercial_build(self):
        decision = evaluate_license("CC BY-NC-SA 4.0", "https://creativecommons.org/licenses/by-nc-sa/4.0/", commercial_build=True)
        self.assertFalse(decision.allowed)
        self.assertFalse(decision.commercial_allowed)


if __name__ == "__main__":
    unittest.main()

