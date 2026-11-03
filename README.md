# ZGIF Converter

MP4 / MOV / WebM などの動画を、チャット用の動くスタンプ `.zgif` に変換するソフトです。
提供された `rickroll.zgif` の構造をもとにした、ZGIF v1の最初の実装です。

## インストール

Python 3.10以上が必要です。リポジトリのフォルダーで実行してください。

```sh
python -m pip install -e .
```

環境によっては `python` の代わりに `python3` を使います。
依存の `imageio-ffmpeg` が対応環境向けのFFmpegを提供します。
PATHにインストール済みのFFmpegがあればそちらを優先します。
任意の実行ファイルは環境変数 `ZGIF_FFMPEG` で指定できます。
外部のFFmpegがあれば、このフォルダーから `python -m zgif_converter` を直接実行することもできます。

## 画面から使う

```sh
python -m zgif_converter --gui
```

「入力動画」と「保存先」を選び、「ZGIFに変換」を押してください。
幅・高さ・FPS・JPEG品質・切り出す開始秒と長さ・透過色を指定できます。
既存ファイルへの上書きには確認を表示します。変換は画面を止めずに実行します。

画面にはTkが必要です。Ubuntu / Debianで不足している場合:

```sh
sudo apt install python3-tk
```

Windows / macOSではTkを含むPython配布を使用してください。

## コマンドから使う

```sh
python -m zgif_converter input.mp4 -o sticker.zgif
python -m zgif_converter input.mov -o short.zgif --start 2 --duration 3 --fps 15 --width 512 --height 512
python -m zgif_converter input.webm -o small.zgif --width 256 --height 256 --quality 8
python -m zgif_converter input.mp4 -o sticker.zgif --key-color '#ff00ff' --overwrite
```

- 既定値: 512×512 / 15fps / JPEG品質3 / 開始0秒 / 最後まで。
- JPEG品質は2〜31。小さいほど高画質で、ファイルは大きくなります。
- 縦横比を保って中央に配置し、余白を透過色で埋めます。
- 既定の透過色は緑 `#00ff00`。サンプルの `y=145, cb=54, cr=34` に対応します。
- 背景の自動除去はしません。被写体に透過色がある場合は別の色を指定してください。
- JPEGは非可逆なので、透過色の境界は完全には一致しません。色の許容差は再生側の実装に依存します。
- 音声は保存しません。透過アルファを保持する形式でもありません。
- 長い動画は画像枚数・一時ディスク使用量・出力容量が大きくなります。スタンプ用には `--duration` で短く切り出してください。
- 出力ファイルは変換成功後に公開します。失敗時は既存ファイルを保持します。

入力形式は利用するFFmpegのデコーダーに依存します。
フレーム抽出にはFFmpegの [image2出力](https://www.ffmpeg.org/ffmpeg-formats.html#image2-2) と
[動画フィルター](https://www.ffmpeg.org/ffmpeg-filters.html) を使用します。

## ファイル構造

```text
sticker.zgif (ZIP)
└── sticker/
    ├── 0.jpg
    ├── 1.jpg
    ├── …
    └── gif.json
```

サンプルのルートフォルダー名は `rickroll` ですが、生成ファイルでは `sticker` に統一しています。
JPEGとJSONはZIP DEFLATE、フォルダーエントリーは無圧縮です。
再生側はフォルダーを見つけ、フレーム名を**数値順**で読み込む想定です。

```json
{
  "version": 1,
  "width": 512,
  "height": 512,
  "fps": 15,
  "transparencyKey": {
    "space": "YCbCr",
    "matrix": "BT.601",
    "range": "limited",
    "y": 145,
    "cb": 54,
    "cr": 34
  }
}
```

このJSONと連番JPEGはサンプルから確認した構造です。ループ動作・色の許容差・ルートフォルダー名の
制約については、再生アプリが未提供のため未検証です。既存プレーヤーとの実機確認が必要です。
サンプル動画自体はリポジトリに含めません。

## 検証

```sh
python -m unittest discover -s tests -v
```

FFmpegが使える環境では短いテスト動画を実際に変換し、連番・画像寸法・メタデータ・切り出し・
失敗時の既存ファイル保護を検証します。FFmpegがない場合、統合テストはスキップします。
