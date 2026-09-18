"""Package the generated PNG as multi-resolution Windows ICO; no visual edits."""
from pathlib import Path
from PIL import Image


def package_icon(source: Path, destination: Path):
    with Image.open(source) as image:
        if image.width != image.height:
            raise ValueError('App icon must be square')
        image.convert('RGBA').save(destination, format='ICO',
            sizes=[(n, n) for n in (16, 24, 32, 48, 64, 128, 256)])


if __name__ == '__main__':
    assets = Path(__file__).resolve().parent.parent / 'src' / 'yys_helper' / 'assets'
    package_icon(assets / 'app-icon.png', assets / 'app-icon.ico')
