# Backends and model provenance

Recognition weights are not included in this repository or release archives.
Consult each upstream license before redistributing or deploying its models.

| Backend | Role | Platform |
| --- | --- | --- |
| PyMuPDF | Text layer, page rendering, native table geometry | macOS / Linux / Windows |
| RapidOCR + ONNX Runtime | PP-OCRv5 detection, PP-OCRv6 Chinese/mixed recognition; English PP-OCRv5 | CPU, portable |
| DocLayout-YOLO | Trained page-region detection | CPU / upstream supported devices |
| DocLayout ONNX conversion | Same model family through ONNX Runtime; no PyTorch | CPU, portable |
| Apple Vision | Independent OCR observations | macOS |
| MLX-VLM + PaddleOCR-VL-1.6 4-bit | Table recognition into OTSL | Apple Silicon macOS |

Layout weights used by `fetch-layout`:
[juliozhao/DocLayout-YOLO-DocStructBench](https://huggingface.co/juliozhao/DocLayout-YOLO-DocStructBench).
File: `doclayout_yolo_docstructbench_imgsz1024.pt`.
You can provide a local weight file; its SHA-256 is included in the run fingerprint.

`demo` downloads the ONNX conversion from
[wybxc/DocLayout-YOLO-DocStructBench-onnx](https://huggingface.co/wybxc/DocLayout-YOLO-DocStructBench-onnx),
**pinned** revision `ee7c3d744e5c47c58e267044ac825f95abe69653`, file
`doclayout_yolo_docstructbench_imgsz1024.onnx` (75,324,598 bytes), SHA-256
`fece9af02f618b603ff7921ccec6861d13e7e1f9830e091dfb7e8ad9311e5b21`.
The model card declares Apache-2.0 and identifies the DocLayout base; embedded
ONNX metadata declares AGPL-3.0. These declarations conflict; this project records
both and does not assert an unqualified Apache-only clearance. Weights are not
bundled. The adapter implementation uses ONNX Runtime directly.

English OCR uses a 2048-pixel maximum detection side and detection box threshold
0.6, compared with the mixed/Chinese threshold 0.5. This reduced icon-stroke false
positives on the brochure while retaining body words. These are development
settings, not evidence of completeness on other sources. Recognition confidence
does not establish whether a region is body or illustration text.

Default MLX model:
[mlx-community/PaddleOCR-VL-1.6-4bit](https://huggingface.co/mlx-community/PaddleOCR-VL-1.6-4bit).
`recognize-tables --model` also accepts a local compatible model directory.
The first selected engine invocation may download weights through upstream libraries.

## License observations (2026-10-11)

The DocLayout model card declares Apache-2.0 at revision
`8c3299a30b8ff29a1503c4431b035b93220f7b11`; its inference code uses AGPL-3.0.
The MLX card declares Apache-2.0 at
`c8987b277bdd8aaec8bd265d154f391bd03ad165`, identifying
`PaddlePaddle/PaddleOCR-VL-1.6` as its base. The base model has a full Apache-2.0
LICENSE at `c5630abae1d940eafe0697512a0325494b02ab42`.
These are checked upstream revisions, not revisions pinned by the current CLI.
Resolve a local model snapshot for deployments requiring exact version control.

RapidOCR 3.10.0's `default_models.yaml` selects these ONNX weights from
`RapidAI/RapidOCR` on ModelScope, revision `v3.10.0`. Its README declares Apache 2.0:

| Role | File | SHA-256 |
| --- | --- | --- |
| Detection | `ch_PP-OCRv5_det_server.onnx` | `0f8846b1d4bba223a2a2f9d9b44022fbc22cc019051a602b41a7fda9667e4cad` |
| Chinese/mixed recognition | `PP-OCRv6_rec_medium.onnx` | `eef444829dbbe18d7fea59a3f6eb75647518d2b3a9568d27c92e42940204894b` |
| English recognition | `en_PP-OCRv5_rec_mobile.onnx` | `c3461add59bb4323ecba96a492ab75e06dda42467c9e3d0c18db5d1d21924be8` |

The project allows newer compatible RapidOCR versions, so their selected weights
may change. A repository-level declaration is not an independent verification of
training-data rights. See the [review](legal-review.zh-CN.md) for source links and
remaining distribution/deployment considerations.

Results are candidates. The native ruled-table fallback rejects missing internal
boundaries instead of inventing merged cells. Borderless or merged raster tables
usually require a dedicated model and source-image review.
