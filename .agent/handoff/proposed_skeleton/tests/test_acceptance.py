"""ACCEPTANCE GATE — the port is 'done' when it reproduces the paper's numbers.

Target (from src_archive/analysis_outputs/analysis_report.md, 25 scenarios, 147 trees):
  - Risk vs albedo:     slope ~ +61 %/unit,  R^2 ~ 0.87
  - Risk vs emissivity: slope ~ -194 %/unit, R^2 ~ 0.64
  - Best: 100% natural landscape (~ -5% vs 50/50 ref)
  - Worst: 100% hard facade      (~ +13% vs 50/50 ref)
Do not ship new science until this passes.
"""
import pytest


@pytest.mark.skip(reason="placeholder — implement after full pipeline port")
def test_reproduces_paper_sensitivity():
    ...
