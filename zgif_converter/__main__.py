import argparse
from pathlib import Path
import sys

from .converter import ConversionError, Options, convert


def main() -> int:
    parser = argparse.ArgumentParser(description="動画をZGIF v1の動くスタンプへ変換します。")
    parser.add_argument("input", nargs="?", type=Path, help="MP4 / MOV / WebMなど")
    parser.add_argument("-o", "--output", type=Path, help="出力先（既定: 入力名.zgif）")
    parser.add_argument("--gui", action="store_true", help="ファイル選択画面を開く")
    parser.add_argument("--width", type=int, default=512)
    parser.add_argument("--height", type=int, default=512)
    parser.add_argument("--fps", type=int, default=15)
    parser.add_argument("--quality", type=int, default=3, help="JPEG品質 2〜31（小さいほど高画質）")
    parser.add_argument("--start", type=float, default=0, help="開始秒")
    parser.add_argument("--duration", type=float, help="変換する秒数（省略で最後まで）")
    parser.add_argument("--key-color", default="#00ff00", help="透過色・余白色 #RRGGBB")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if args.gui:
        from .gui import main as gui_main
        return gui_main()
    if args.input is None:
        parser.error("入力動画を指定するか --gui を指定してください。")
    options = Options(args.width, args.height, args.fps, args.quality,
                      args.start, args.duration, args.key_color)
    try:
        convert(args.input, args.output or args.input.with_suffix(".zgif"), options,
                overwrite=args.overwrite, status=print)
    except (ConversionError, OSError) as exc:
        print(f"エラー: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
