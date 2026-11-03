import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile

from zgif_converter import ConversionError, Options, convert
from zgif_converter.converter import find_ffmpeg, transparency_key


class ValidationTests(unittest.TestCase):
    def test_sample_key(self):
        self.assertEqual(transparency_key("#00ff00"), {
            "space": "YCbCr", "matrix": "BT.601", "range": "limited",
            "y": 145, "cb": 54, "cr": 34})

    def test_invalid_options(self):
        for options in (Options(width=0), Options(fps=0), Options(quality=32),
                        Options(start=-1), Options(start=float("nan")),
                        Options(duration=float("inf")), Options(duration=0),
                        Options(key_color="red")):
            with self.subTest(options=options), self.assertRaises(ConversionError):
                options.validate()

    def test_missing_source(self):
        with self.assertRaises(ConversionError):
            convert("/not-a-real-video.mp4", "output.zgif")


class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.ffmpeg = find_ffmpeg()
        except ConversionError as exc:
            raise unittest.SkipTest(str(exc))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="zgif-test-")
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.source = self.directory / "動画 with spaces.mp4"
        subprocess.run([self.ffmpeg, "-v", "error", "-f", "lavfi", "-i",
                        "testsrc2=size=160x90:rate=30:duration=2", "-c:v", "mpeg4",
                        "-y", str(self.source)], check=True, capture_output=True)

    def inspect(self, output, count, width, height, fps):
        with zipfile.ZipFile(output) as z:
            self.assertIsNone(z.testzip())
            metadata = json.loads(z.read("sticker/gif.json"))
            self.assertEqual(metadata, {"version": 1, "width": width, "height": height,
                                      "fps": fps, "transparencyKey": transparency_key("#00ff00")})
            self.assertEqual([n for n in z.namelist() if n.endswith(".jpg")],
                             [f"sticker/{i}.jpg" for i in range(count)])
            jpeg = self.directory / "frame.jpg"
            jpeg.write_bytes(z.read("sticker/0.jpg"))
        # Decode the output JPEG to RGB bytes; verifies both readability and dimensions.
        result = subprocess.run([self.ffmpeg, "-v", "error", "-i", str(jpeg),
                                 "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                                capture_output=True, check=True)
        self.assertEqual(len(result.stdout), width * height * 3)

    def test_full_video_and_default_metadata(self):
        output = self.directory / "動くスタンプ.zgif"
        self.assertEqual(convert(self.source, output), output)
        self.inspect(output, 30, 512, 512, 15)

    def test_trim_resize_and_green_padding(self):
        output = self.directory / "short.zgif"
        convert(self.source, output, Options(width=128, height=128, fps=10, start=0.5, duration=0.5))
        self.inspect(output, 5, 128, 128, 10)
        raw = subprocess.run([self.ffmpeg, "-v", "error", "-i", str(self.directory / "frame.jpg"),
                              "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                             check=True, capture_output=True).stdout
        r, g, b = raw[:3]
        self.assertLess(r, 15)
        self.assertGreater(g, 240)
        self.assertLess(b, 15)

    def test_refuses_overwrite(self):
        output = self.directory / "existing.zgif"
        output.write_bytes(b"keep me")
        with self.assertRaises(ConversionError):
            convert(self.source, output)
        self.assertEqual(output.read_bytes(), b"keep me")

    def test_failed_conversion_preserves_existing_file(self):
        self.source.write_bytes(b"not a video")
        output = self.directory / "existing.zgif"
        output.write_bytes(b"keep me")
        with self.assertRaises(ConversionError):
            convert(self.source, output, overwrite=True)
        self.assertEqual(output.read_bytes(), b"keep me")
        self.assertFalse(list(self.directory.glob(".zgif-*")))

    def test_successful_overwrite(self):
        output = self.directory / "existing.zgif"
        output.write_bytes(b"old")
        convert(self.source, output, Options(duration=0.2), overwrite=True)
        self.inspect(output, 3, 512, 512, 15)

    def test_start_beyond_end_does_not_create_output(self):
        output = self.directory / "empty.zgif"
        with self.assertRaises(ConversionError):
            convert(self.source, output, Options(start=99))
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
