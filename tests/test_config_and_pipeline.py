import os
import shutil

import pandas as pd
import pytest
import yaml

from cda.pipeline.config_loader import AppConfig
from cda.pipeline.main import main

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "test", "input_file")


def test_default_yaml_has_relative_paths():
    cfg = AppConfig.from_yaml(os.path.join(ROOT, "config", "default.yaml"))
    for p in vars(cfg.paths).values():
        assert not os.path.isabs(p)


@pytest.mark.skipif(not any(f.endswith(".json") for f in os.listdir(RAW)),
                    reason="no measurement JSON in test/input_file")
def test_pipeline_end_to_end_has_no_nan(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    jsons = sorted(f for f in os.listdir(RAW) if f.endswith(".json"))[:1]
    for f in jsons:
        shutil.copy(os.path.join(RAW, f), raw / f)

    with open(os.path.join(ROOT, "config", "default.yaml")) as fh:
        raw_cfg = yaml.safe_load(fh)
    raw_cfg["paths"] = {
        "raw_data": str(raw),
        "output_csv": str(tmp_path / "csv"),
        "output_plots": str(tmp_path / "plots"),
        "output_preprocessed": str(tmp_path / "pre"),
    }
    cfg_path = tmp_path / "cfg.yaml"
    cfg_path.write_text(yaml.safe_dump(raw_cfg))

    out = main(str(cfg_path))
    assert set(out["preprocessed"]) == {os.path.splitext(f)[0] for f in jsons}
    for test_id, runs in out["preprocessed"].items():
        assert set(runs) == {"no_wind", "with_wind"}
        assert out["calibrations"][test_id][0].method == "fit"
        for df in runs.values():
            assert not df.isna().any().any()
            assert df["segment"].nunique() == raw_cfg["segment"]["segment_num"]
            assert 5 < df["v"].mean() < 25              # m/s, not km/h or /3.6 twice
            assert {"valid", "is_bend", "load_factor"} <= set(df.columns)
        assert (runs["no_wind"]["v_wind"] == 0).all()
