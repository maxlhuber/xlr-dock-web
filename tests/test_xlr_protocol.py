import unittest

from xlr_control.protocol import XlrConfig, clamp_mix_percent


class XlrProtocolTests(unittest.TestCase):
    def test_config_roundtrip_monitor_mix(self):
        config = XlrConfig.empty()
        config.monitor_mix = 25

        parsed = XlrConfig.from_bytes(config.to_bytes())

        self.assertEqual(parsed.monitor_mix, 25)
        self.assertEqual(parsed.raw[12], 0)

    def test_config_monitor_mix_stray_bits(self):
        config = XlrConfig.empty()

        config.monitor_mix = 41
        self.assertEqual(config.raw[12], 1)

        config.monitor_mix = 50
        self.assertEqual(config.raw[12], 0)

    def test_config_preserves_phantom_when_changing_mix(self):
        config = XlrConfig.empty()
        config.phantom_power = True

        config.monitor_mix = 75

        self.assertIs(config.phantom_power, True)
        self.assertEqual(config.raw[6], 1)

    def test_clamp_mix_percent(self):
        self.assertEqual(clamp_mix_percent(-10), 0)
        self.assertEqual(clamp_mix_percent(24.6), 25)
        self.assertEqual(clamp_mix_percent(110), 100)


if __name__ == "__main__":
    unittest.main()
