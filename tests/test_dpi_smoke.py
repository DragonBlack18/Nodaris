import json
import os
import subprocess
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class DpiSmokeTests(unittest.TestCase):

    def test_all_release_scale_factors(self):
        for scale in ("1.0", "1.25", "1.5"):
            with self.subTest(scale=scale):
                environment = dict(os.environ)
                environment["QT_QPA_PLATFORM"] = "offscreen"
                environment["QT_SCALE_FACTOR"] = scale

                result = subprocess.run(
                    [
                        sys.executable,
                        str(
                            PROJECT_ROOT
                            / "scripts"
                            / "dpi_smoke.py"
                        ),
                        "--scale",
                        scale,
                    ],
                    cwd=PROJECT_ROOT,
                    env=environment,
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=45,
                )

                output_lines = [
                    line
                    for line in result.stdout.splitlines()
                    if line.strip()
                ]
                self.assertTrue(
                    output_lines,
                    msg=result.stderr,
                )
                report = json.loads(output_lines[-1])
                self.assertEqual(
                    result.returncode,
                    0,
                    msg=json.dumps(
                        report,
                        ensure_ascii=False,
                        indent=2,
                    )
                    + "\n"
                    + result.stderr,
                )
                self.assertTrue(report["ok"])


if __name__ == "__main__":
    unittest.main()
