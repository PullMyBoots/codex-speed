import importlib.util
import math
from pathlib import Path
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('renderer',Path(__file__).resolve().parents[1]/'render.py')
renderer=importlib.util.module_from_spec(spec);spec.loader.exec_module(renderer)


class RenderTests(unittest.TestCase):
    def test_phases_and_invalid_samples(self):
        cases=[({},'Decode: —'),({'phase':'streaming','output_tps':42.5},'Decode: ~42.5 t/s'),({'phase':'streaming','stream_kind':'tool','output_tps':42.5},'Decode (tool): ~42.5 t/s'),({'phase':'streaming','stream_kind':'reasoning','output_tps':42.5},'Decode (think): ~42.5 t/s'),({'phase':'streaming','stream_kind':'summary','output_tps':20},'Summary: ~20.0 t/s'),({'phase':'waiting','output_tps':42.5},'Decode (last): ~42.5 t/s'),({'phase':'complete','output_tps':40},'Decode (last): ~40.0 t/s'),({'phase':'interrupted','output_tps':0},'Decode (stopped): ~0.0 t/s')]
        for metrics,expected in cases:
            with self.subTest(metrics=metrics):self.assertEqual(renderer.render({'stream_metrics':metrics}),expected)
        for invalid in (True,-1,'50',math.inf,math.nan):
            with self.subTest(invalid=invalid):self.assertEqual(renderer.render({'stream_metrics':{'output_tps':invalid}}),'Decode: —')

    def test_no_rate_from_cumulative_usage(self):
        self.assertEqual(renderer.render({'usage':{'output_tokens':999999}}),'Decode: — | Out: 999,999')

    def test_terminal_width_and_invalid_width(self):
        with patch.dict('os.environ',{'CXSTATUSLINE_WIDTH':'12'}):self.assertEqual(len(renderer.render({})),9)
        with patch.dict('os.environ',{'CXSTATUSLINE_WIDTH':'invalid'}):self.assertEqual(renderer.render({}),'Decode: —')
        with patch.dict('os.environ',{'CXSTATUSLINE_WIDTH':'3'}):self.assertEqual(renderer.render({}),'Dec')


if __name__=='__main__':unittest.main()
