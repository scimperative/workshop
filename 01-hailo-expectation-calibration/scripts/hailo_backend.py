"""Inference backends.

HailoBackend : real HailoRT (hailo_platform) on the Pi. Uses the InferVStreams API.
SimBackend   : NO hardware. Sleeps and returns fake detections so the logging/analysis
               pipeline can be smoke-tested on a laptop. Runs are flagged simulated=true
               and analyse.py refuses them unless --allow-simulated.
"""
from __future__ import annotations

import time
from contextlib import ExitStack

import numpy as np


class SimBackend:
    simulated = True
    has_nms = True
    name = "sim"

    def __init__(self, hef_path=None, per_frame_s=0.004, device_batch=1, **_):
        self.device_batch = device_batch
        self.input_shape = (640, 640, 3)
        self.per_frame_s = per_frame_s
        self.hef_path = hef_path

    def open(self):
        return self

    def close(self):
        pass

    def chip_temps(self):
        return {}

    def infer(self, batch):
        n = batch.shape[0]
        time.sleep(self.per_frame_s * n)
        frames = []
        for _ in range(n):
            cls_list = [np.zeros((0, 5), np.float32) for _ in range(80)]
            cls_list[0] = np.array([[0.1, 0.1, 0.5, 0.5, 0.9]], np.float32)  # ymin,xmin,ymax,xmax,score
            frames.append(cls_list)
        return {"sim_nms": frames}

    def output_name(self):
        return "sim_nms"

    def version(self):
        return "sim"


class HailoBackend:
    simulated = False
    name = "hailo"

    def __init__(self, hef_path, device_batch=1, **_):
        self.hef_path = hef_path
        self.device_batch = device_batch
        self.stack = ExitStack()

    @staticmethod
    def _vparams(cls, ng, fmt):
        # `quantized` was deprecated in newer HailoRT; support both signatures.
        try:
            return cls.make_from_network_group(ng, quantized=False, format_type=fmt)
        except TypeError:
            return cls.make_from_network_group(ng, format_type=fmt)

    def open(self):
        from hailo_platform import (  # imported here so the sim backend works without HailoRT
            HEF,
            ConfigureParams,
            FormatType,
            HailoStreamInterface,
            InferVStreams,
            InputVStreamParams,
            OutputVStreamParams,
            VDevice,
        )

        self.hef = HEF(self.hef_path)
        self.target = self.stack.enter_context(VDevice())
        cfg = ConfigureParams.create_from_hef(self.hef, interface=HailoStreamInterface.PCIe)
        if self.device_batch > 1:  # device-side batch (context-switch amortisation). Default 1 = pre-registered config.
            # create_from_hef returns {network_group_name: ConfigureNetworkParams} on HailoRT 4.20
            groups = cfg.values() if isinstance(cfg, dict) else cfg.network_group_params.values()
            for p in groups:
                p.batch_size = self.device_batch
        self.ng = self.target.configure(self.hef, cfg)[0]
        self.ng_params = self.ng.create_params()
        in_p = self._vparams(InputVStreamParams, self.ng, FormatType.UINT8)
        out_p = self._vparams(OutputVStreamParams, self.ng, FormatType.FLOAT32)
        self.in_info = self.hef.get_input_vstream_infos()[0]
        self.out_infos = self.hef.get_output_vstream_infos()
        self.input_shape = tuple(self.in_info.shape)
        self.has_nms = any("NMS" in str(i.format.order).upper() for i in self.out_infos)
        self.pipeline = self.stack.enter_context(InferVStreams(self.ng, in_p, out_p))
        self.stack.enter_context(self.ng.activate(self.ng_params))
        return self

    def close(self):
        self.stack.close()

    def output_name(self):
        return self.out_infos[0].name

    def infer(self, batch):
        return self.pipeline.infer({self.in_info.name: np.ascontiguousarray(batch)})

    def chip_temps(self):
        """Hailo die temperature sensors, if the control API exposes them."""
        try:
            dev = self.target.get_physical_devices()[0]
            t = dev.control.get_chip_temperature()
            return {"hailo_ts0_c": float(t.ts0_temperature), "hailo_ts1_c": float(t.ts1_temperature)}
        except Exception:
            return {}

    def version(self):
        try:
            import hailo_platform

            return getattr(hailo_platform, "__version__", "unknown")
        except Exception:
            return "unknown"


def make_backend(kind, hef_path, device_batch=1):
    if kind == "sim":
        return SimBackend(hef_path, device_batch=device_batch)
    if kind == "hailo":
        return HailoBackend(hef_path, device_batch=device_batch)
    raise ValueError(kind)
