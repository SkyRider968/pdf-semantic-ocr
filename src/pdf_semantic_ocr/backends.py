"""Optional model adapters; heavy dependencies are imported only when selected."""
from __future__ import annotations

import io
import ast
import sys

import numpy as np


class RapidBackend:
    name = "rapidocr"

    def __init__(self, language="auto", threads=4):
        try:
            from rapidocr import LangRec, ModelType, OCRVersion, RapidOCR
        except ImportError as error:
            raise ValueError("Install OCR dependencies: pip install '.[ocr]' from the checkout, or install the release wheel with [ocr]") from error
        self.engine = RapidOCR(params={
            "Det.ocr_version": OCRVersion.PPOCRV5, "Det.model_type": ModelType.SERVER,
            "Rec.ocr_version": OCRVersion.PPOCRV5 if language == "en" else OCRVersion.PPOCRV6,
            "Rec.model_type": ModelType.MOBILE if language == "en" else ModelType.MEDIUM,
            "Rec.lang_type": LangRec.EN if language == "en" else LangRec.CH,
            "Global.text_score": 0.3, "Det.limit_side_len": 2048, "Det.limit_type": "max",
            "Det.box_thresh": 0.6 if language == "en" else 0.5,
            "EngineConfig.onnxruntime.intra_op_num_threads": threads,
            "EngineConfig.onnxruntime.inter_op_num_threads": 1,
            "Global.log_level": "warning",
        })

    def recognize(self, image):
        result = self.engine(np.array(image)[:, :, ::-1], use_cls=False)
        if result.txts is None:
            return []
        return [{"text": text, "confidence": float(score),
                 "bbox": [float(box[:, 0].min()), float(box[:, 1].min()),
                          float(box[:, 0].max()), float(box[:, 1].max())]}
                for box, text, score in zip(result.boxes, result.txts, result.scores)]


class VisionBackend:
    name = "apple-vision"

    def __init__(self, language="auto", **_):
        if sys.platform != "darwin":
            raise ValueError("Apple Vision requires macOS; use --ocr-backend rapidocr")
        try:
            import Foundation
            import Vision
            import objc
        except ImportError as error:
            raise ValueError("Install Apple Vision dependencies: pip install '.[vision]' from the checkout, or install the release wheel with [vision]") from error
        self.Foundation, self.Vision, self.objc = Foundation, Vision, objc
        self.language = language

    def recognize(self, image):
        with self.objc.autorelease_pool():
            stream = io.BytesIO()
            image.save(stream, format="PNG")
            data = self.Foundation.NSData.dataWithBytes_length_(stream.getvalue(), len(stream.getvalue()))
            request = self.Vision.VNRecognizeTextRequest.alloc().init()
            request.setRecognitionLevel_(self.Vision.VNRequestTextRecognitionLevelAccurate)
            request.setRecognitionLanguages_(["en-US"] if self.language == "en" else ["zh-Hans", "en-US"])
            request.setUsesLanguageCorrection_(False)
            handler = self.Vision.VNImageRequestHandler.alloc().initWithData_options_(data, {})
            success, error = handler.performRequests_error_([request], None)
            if not success:
                raise RuntimeError(str(error))
            result = []
            for observation in request.results():
                candidate = observation.topCandidates_(1)[0]
                b = observation.boundingBox()
                result.append({"text": str(candidate.string()), "confidence": float(candidate.confidence()),
                               "bbox": [b.origin.x * image.width, (1 - b.origin.y - b.size.height) * image.height,
                                        (b.origin.x + b.size.width) * image.width,
                                        (1 - b.origin.y) * image.height]})
            return result


def ocr_backend(name, language="auto", threads=4):
    return (RapidBackend if name == "rapidocr" else VisionBackend)(language=language, threads=threads)


class DocLayoutBackend:
    def __init__(self, weights):
        try:
            from doclayout_yolo import YOLOv10
            import torch
        except ImportError as error:
            raise ValueError("Install layout dependencies: pip install '.[layout]' from the checkout, or install the release wheel with [layout]") from error
        torch.set_num_threads(4)
        self.engine = YOLOv10(str(weights))

    def detect(self, image):
        prediction = self.engine.predict(np.array(image), imgsz=1024, conf=0.25,
                                         device="cpu", verbose=False)[0]
        mapping = {"plain text": "text", "title": "title", "figure": "figure",
                   "figure_caption": "figure_caption", "table": "table", "table_caption": "table_caption",
                   "table_footnote": "table_footnote", "isolate_formula": "formula",
                   "formula_caption": "figure_caption", "abandon": "unassigned"}
        regions = []
        from .geometry import area, overlap
        for box in sorted(prediction.boxes, key=lambda b: -float(b.conf)):
            rect = box.xyxy[0].tolist()
            if any(overlap(rect, r["bbox"]) / max(1, min(area(rect), area(r["bbox"]))) > 0.9 for r in regions):
                continue
            regions.append({"kind": mapping.get(prediction.names[int(box.cls)], "unassigned"),
                            "bbox": rect, "confidence": float(box.conf), "method": "doclayout-yolo"})
        return regions

class ONNXLayoutBackend:
    """Run the published DocLayout conversion without a PyTorch installation."""
    def __init__(self, weights):
        try:
            import onnxruntime as ort
        except ImportError as error:
            raise ValueError("Install ONNX Runtime with the [ocr] extra") from error
        options = ort.SessionOptions()
        options.intra_op_num_threads = 4
        options.inter_op_num_threads = 1
        self.engine = ort.InferenceSession(str(weights), options, providers=["CPUExecutionProvider"])
        self.names = ast.literal_eval(self.engine.get_modelmeta().custom_metadata_map["names"])
        self.input_name = self.engine.get_inputs()[0].name
        self.size = 1024

    def detect(self, image):
        import cv2
        from .geometry import area, overlap
        width, height = image.size
        ratio = min(self.size / width, self.size / height)
        resized = cv2.resize(np.array(image.convert("RGB")), (round(width * ratio), round(height * ratio)))
        left = (self.size - resized.shape[1]) // 2
        top = (self.size - resized.shape[0]) // 2
        canvas = np.full((self.size, self.size, 3), 114, dtype=np.uint8)
        canvas[top:top + resized.shape[0], left:left + resized.shape[1]] = resized
        tensor = canvas.transpose(2, 0, 1)[None].astype(np.float32) / 255.0
        prediction = self.engine.run(None, {self.input_name: tensor})[0]
        if prediction.ndim != 3 or prediction.shape[-1] != 6:
            raise ValueError("Unsupported layout ONNX output; expected batch x detections x 6")
        mapping = {"plain text": "text", "title": "title", "figure": "figure",
                   "figure_caption": "figure_caption", "table": "table", "table_caption": "table_caption",
                   "table_footnote": "table_footnote", "isolate_formula": "formula",
                   "formula_caption": "figure_caption", "abandon": "unassigned"}
        regions = []
        for box in sorted(prediction[0], key=lambda b: -float(b[4])):
            if not np.isfinite(box).all() or box[4] < 0.25:
                continue
            rect = ((box[:4] - np.array([left, top, left, top])) / ratio).tolist()
            rect = [max(0, rect[0]), max(0, rect[1]), min(width, rect[2]), min(height, rect[3])]
            if area(rect) <= 0:
                continue
            if any(overlap(rect, r["bbox"]) / max(1, min(area(rect), area(r["bbox"]))) > 0.9 for r in regions):
                continue
            regions.append({"kind": mapping.get(self.names.get(int(box[5])), "unassigned"),
                            "bbox": rect, "confidence": float(box[4]), "method": "doclayout-onnx"})
        return regions


class MLXTableBackend:
    def __init__(self, model="mlx-community/PaddleOCR-VL-1.6-4bit"):
        if sys.platform != "darwin":
            raise ValueError("MLX table recognition requires Apple Silicon macOS; use import-candidate")
        try:
            from mlx_vlm import load
            from mlx_vlm.prompt_utils import apply_chat_template
        except ImportError as error:
            raise ValueError("Install table dependencies: pip install '.[mlx]' from the checkout, or install the release wheel with [mlx]") from error
        self.model_id = model
        self.model, self.processor = load(model)
        self.prompt = apply_chat_template(self.processor, self.model.config, "Table Recognition:", num_images=1)

    def recognize(self, crop):
        from mlx_vlm import generate
        result = generate(self.model, self.processor, self.prompt, image=[crop],
                          max_tokens=8192, temperature=0, verbose=False)
        return result.text
