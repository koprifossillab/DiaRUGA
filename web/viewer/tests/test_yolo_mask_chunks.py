"""YOLO 의 원본 크기 마스크를 나눠 만든다 (245 · `segment_diatoms.chunked_mask_fn`).

**나눠 불러 이어 붙인 것이 한 번에 부른 것과 같아야 한다.** 다르면 검출과 마스크의 짝이
어긋나 개체마다 남의 윤곽이 붙는다 — 예외 없이 틀리는 종류다. 여기서는 감싸기의 자르기·
이어 붙이기만 본다(진짜 `process_mask_native` 는 ultralytics 가 있어야 돈다 — 그쪽 비교는
파이프라인 이미지에서 했다 · 245 4절·7절).

`segment_diatoms` 는 cv2·torch 를 머리에서 임포트한다 — 없으면 건너뛴다(`test_save_detection_cleanup` 과 같다).
"""
import importlib.util
import unittest

from .base import DiaRUGATestCase

HAS = (importlib.util.find_spec("cv2") is not None
       and importlib.util.find_spec("torch") is not None)
if HAS:
    import torch

    import segment_diatoms


def _fake_native(protos, masks_in, bboxes, shape):
    """`process_mask_native` 와 같은 모양 — 검출마다 계수·상자에 따라 다른 (H, W) 를 낸다.

    프로토타입은 모두가 같이 쓰고, 계수와 상자는 검출마다다. 자르기를 하나라도 틀리게 하면
    (상자를 안 자르거나 계수와 어긋나게) 값이나 모양이 달라진다.
    """
    c = protos.shape[0]
    m = (masks_in @ protos.view(c, -1)).view(-1, *protos.shape[1:])
    m = torch.nn.functional.interpolate(m[None], shape, mode="bilinear")[0]
    h, w = shape
    r = torch.arange(w)[None, None, :]
    cc = torch.arange(h)[None, :, None]
    x1, y1, x2, y2 = torch.chunk(bboxes[:, :, None], 4, 1)
    return (m * ((r >= x1) * (r < x2) * (cc >= y1) * (cc < y2))).gt_(0.0).byte()


@unittest.skipUnless(HAS, "cv2·torch 가 없다 — 파이프라인 이미지에서 돈다")
class ChunkedMaskTest(DiaRUGATestCase):

    def material(self, n):
        g = torch.Generator().manual_seed(0)
        protos = torch.randn(8, 20, 24, generator=g)
        masks_in = torch.randn(n, 8, generator=g)
        xy = torch.rand(n, 2, generator=g) * 60
        bboxes = torch.cat([xy, xy + 10 + torch.rand(n, 2, generator=g) * 30], 1)
        return protos, masks_in, bboxes, (80, 96)

    def test_나눠_만든_것이_한_번에_만든_것과_같다(self):
        args = self.material(50)                       # 16 · 16 · 16 · 2 로 나뉜다
        full = _fake_native(*args)
        got = segment_diatoms.chunked_mask_fn(_fake_native, 16)(*args)
        self.assertEqual(got.shape, full.shape)
        self.assertTrue(torch.equal(got, full))

    def test_나누는_수보다_적으면_그대로_부른다(self):
        calls = []

        def spy(*a):
            calls.append(len(a[1]))
            return _fake_native(*a)
        segment_diatoms.chunked_mask_fn(spy, 16)(*self.material(16))
        self.assertEqual(calls, [16])

    def test_나눠_부른다(self):
        calls = []

        def spy(*a):
            calls.append(len(a[1]))
            return _fake_native(*a)
        segment_diatoms.chunked_mask_fn(spy, 16)(*self.material(50))
        self.assertEqual(calls, [16, 16, 16, 2])

    def test_두_번_끼워도_한_겹이다(self):
        """바꿔 끼운 함수를 또 감싸면 나누기가 겹쳐 돈다 — 값은 같아도 원래 함수를 잃는다."""
        if importlib.util.find_spec("ultralytics") is None:
            self.skipTest("ultralytics 가 없다 — 파이프라인 이미지에서 돈다")
        import ultralytics.utils.ops as ops
        before = ops.process_mask_native
        try:
            segment_diatoms.install_chunked_masks()
            once = ops.process_mask_native
            segment_diatoms.install_chunked_masks()
            self.assertIs(ops.process_mask_native, once)
            self.assertEqual(once.chunked, segment_diatoms.MASK_CHUNK)
        finally:
            ops.process_mask_native = getattr(before, "orig", before)
