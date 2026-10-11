# Third-party projects

This project calls upstream libraries; it does not bundle their source or weights.

| Project | Upstream | License / notice |
| --- | --- | --- |
| PyMuPDF | https://github.com/pymupdf/PyMuPDF | AGPL-3.0 or commercial license |
| DocLayout-YOLO | https://github.com/opendatalab/DocLayout-YOLO | AGPL-3.0; see separate model terms |
| RapidOCR | https://github.com/RapidAI/RapidOCR | Apache-2.0 |
| PaddleOCR | https://github.com/PaddlePaddle/PaddleOCR | Apache-2.0; model terms remain upstream |
| ONNX Runtime | https://github.com/microsoft/onnxruntime | MIT |
| MLX-VLM | https://github.com/Blaizzy/mlx-vlm | MIT |
| OpenCV | https://github.com/opencv/opencv | Apache-2.0 |
| NumPy | https://github.com/numpy/numpy | BSD-3-Clause |
| Pillow | https://github.com/python-pillow/Pillow | MIT-CMU (historical versions/metadata may use HPND wording) |
| PyObjC | https://github.com/ronaldoussoren/pyobjc | MIT; Apple frameworks remain Apple's |

The public fixture text,
tables and diagrams in `examples/` are original synthetic examples. The additional
USDA/HHS 2020 federal-publication original, raster derivative and attribution
are described in [demo provenance](docs/demo.md). No user-provided source documents or extracts are distributed. The built-in CJK font is used by PyMuPDF to
generate fixture pages; no standalone font file is included. These digital fixtures
embed Droid Sans Fallback Regular, from the Android/Droid fonts distributed with
MuPDF (Apache-2.0). The font's license is included in `LICENSES/Apache-2.0.txt`.
The font copyright notice is in `LICENSES/Droid-font-NOTICE.txt`.

Code and model licenses are separate. The checked DocLayout weight card declares
Apache-2.0 while its inference library uses AGPL-3.0. PaddleOCR-VL-1.6 and the
selected MLX quantization declare Apache-2.0. RapidAI's selected model hosting
repository also declares Apache-2.0. Exact checked references and qualifications
are in [the dated review](docs/legal-review.zh-CN.md) and [model provenance](docs/models.md).
This table covers the selected primary libraries, not every transitive component
of future wheels, containers or upstream binary distributions. Preserve their
bundled license/notice files when redistributing them.

The optional ONNX DocLayout conversion is downloaded from
`wybxc/DocLayout-YOLO-DocStructBench-onnx`. Its model card declares Apache-2.0;
embedded ONNX metadata declares AGPL-3.0. Both are recorded in `docs/models.md`.
The conversion and upstream inference source are not bundled with this release.
