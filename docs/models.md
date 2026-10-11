# Backends and model provenance

Recognition weights are not included in this repository or release archives.
Consult each upstream license before redistributing or deploying its models.

| Backend | Role | Platform |
| --- | --- | --- |
| PyMuPDF | Text layer, page rendering, native table geometry | macOS / Linux / Windows |
| RapidOCR + ONNX Runtime | PP-OCRv5 detection, PP-OCRv6 Chinese/mixed recognition; English PP-OCRv5 | CPU, portable |
| DocLayout-YOLO | Trained page-region detection | CPU / upstream supported devices |
| Apple Vision | Independent OCR observations | macOS |
| MLX-VLM + PaddleOCR-VL-1.6 4-bit | Table recognition into OTSL | Apple Silicon macOS |

Layout weights used by `fetch-layout`:
[juliozhao/DocLayout-YOLO-DocStructBench](https://huggingface.co/juliozhao/DocLayout-YOLO-DocStructBench).
File: `doclayout_yolo_docstructbench_imgsz1024.pt`.
You can provide a local weight file; its SHA-256 is included in the run fingerprint.

Default MLX model:
[mlx-community/PaddleOCR-VL-1.6-4bit](https://huggingface.co/mlx-community/PaddleOCR-VL-1.6-4bit).
`recognize-tables --model` also accepts a local compatible model directory.
The first selected engine invocation may download weights through upstream libraries.

Results are candidates. The native ruled-table fallback rejects missing internal
boundaries instead of inventing merged cells. Borderless or merged raster tables
usually require a dedicated model and source-image review.
