#!/usr/bin/env python3
"""mAP50-95 on the committed 500-image COCO subset.

  INT8 on Hailo : python scripts/eval_accuracy.py --backend hailo --model models/yolov8n_h8l.hef
  FP32 baseline : python scripts/eval_accuracy.py --backend onnx  --model models/yolov8n.onnx
                  (export once on a laptop:  yolo export model=yolov8n.pt format=onnx imgsz=640 opset=12)
Writes data/raw/accuracy_<backend>.json. analyse.py reports the delta.

Note: the Hailo model-zoo HEFs bake in an NMS score threshold; if it is high (e.g. 0.2) mAP is
lower than a 0.001-threshold FP32 evaluation. The threshold used for FP32 is recorded and can be
raised with --conf to compare like-for-like."""
import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

COCO = common.ROOT / "data" / "coco"


def run_hailo(model, items, size):
    from hailo_backend import HailoBackend

    be = HailoBackend(model).open()
    if not be.has_nms:
        raise SystemExit("This HEF has raw outputs (no on-chip/HailoRT NMS); eval_accuracy supports NMS HEFs only.")
    name = be.output_name()
    results = []
    try:
        for n, (img_id, path) in enumerate(items):
            rgb, meta = common.load_and_letterbox(path, size)
            out = be.infer(rgb[None])[name]
            d = common.boxes_to_original(common.parse_nms_output(out, 0, 0.0), meta, size)
            results.append((img_id, d))
            if n % 100 == 0:
                print(f"  {n}/{len(items)}")
    finally:
        be.close()
    return results, "hailo NMS threshold set at compile time (not controllable here)"


def run_onnx(model, items, size, conf):
    import cv2
    import onnxruntime as ort

    sess = ort.InferenceSession(model, providers=["CPUExecutionProvider"])
    inp = sess.get_inputs()[0].name
    results = []
    for n, (img_id, path) in enumerate(items):
        rgb, meta = common.load_and_letterbox(path, size)
        x = (rgb.astype(np.float32) / 255.0).transpose(2, 0, 1)[None]
        p = sess.run(None, {inp: x})[0][0].T  # (8400, 84)
        scores = p[:, 4:]
        cls = scores.argmax(1)
        sc = scores.max(1)
        m = sc >= conf
        p, cls, sc = p[m], cls[m], sc[m]
        if len(sc) == 0:
            results.append((img_id, np.zeros((0, 6), np.float32)))
            continue
        cx, cy, w, h = p[:, 0], p[:, 1], p[:, 2], p[:, 3]
        xyxy = np.stack([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], 1)
        off = cls[:, None] * 4096.0  # class-offset trick => per-class NMS
        tl = np.stack([xyxy[:, 0] + off[:, 0], xyxy[:, 1] + off[:, 0], w, h], 1)
        keep = np.asarray(cv2.dnn.NMSBoxes(tl.tolist(), sc.tolist(), conf, 0.7)).reshape(-1)[:300]
        dets = np.hstack([xyxy[keep] / size, sc[keep, None], cls[keep, None]]).astype(np.float32)
        results.append((img_id, common.boxes_to_original(dets, meta, size)))
        if n % 100 == 0:
            print(f"  {n}/{len(items)}")
    return results, f"onnx conf threshold {conf}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=["hailo", "onnx"], required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--conf", type=float, default=0.001)
    ap.add_argument("--max-images", type=int, default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    from pycocotools.coco import COCO as C
    from pycocotools.cocoeval import COCOeval

    items = common.list_dataset()[: a.max_images]
    gt = C(str(COCO / "instances_val2017_subset500.json"))
    cat_ids = sorted(gt.getCatIds())
    size = common.load_config()["imgsz"]
    results, note = run_hailo(a.model, items, size) if a.backend == "hailo" else run_onnx(a.model, items, size, a.conf)

    dt = []
    for img_id, d in results:
        for x0, y0, x1, y1, s, c in d:
            dt.append({"image_id": img_id, "category_id": cat_ids[int(c)], "bbox": [float(x0), float(y0), float(x1 - x0), float(y1 - y0)], "score": float(s)})
    if not dt:
        raise SystemExit("No detections produced; cannot evaluate.")
    E = COCOeval(gt, gt.loadRes(dt), "bbox")
    E.params.imgIds = [i for i, _ in items]
    E.evaluate(); E.accumulate(); E.summarize()
    out = {"backend": a.backend, "model": a.model, "model_sha256": common.sha256_file(a.model),
           "n_images": len(items), "map50_95": float(E.stats[0]), "map50": float(E.stats[1]), "note": note}
    p = a.out or str(common.ROOT / "data" / "raw" / f"accuracy_{a.backend}.json")
    with open(p, "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
