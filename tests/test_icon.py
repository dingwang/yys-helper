from pathlib import Path
import tempfile
import unittest
from PIL import Image
from scripts.package_icon import package_icon


class IconTests(unittest.TestCase):
    def test_generated_icon_exports_all_windows_sizes_with_alpha(self):
        source = Path(__file__).resolve().parents[1] / 'src/yys_helper/assets/app-icon.png'
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'icon.ico'
            package_icon(source, output)
            with Image.open(output) as icon:
                self.assertEqual({(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)}, icon.ico.sizes())
                self.assertEqual('RGBA', icon.ico.getimage((32, 32)).mode)
