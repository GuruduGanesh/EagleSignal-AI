import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def uptrend_df() -> pd.DataFrame:
    n = 260
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    close = pd.Series(np.linspace(100, 200, n), index=idx)
    return pd.DataFrame({
        "open": close * 0.99, "high": close * 1.01,
        "low": close * 0.98, "close": close,
        "volume": pd.Series(np.full(n, 5_000_000.0), index=idx),
    })


@pytest.fixture
def downtrend_df() -> pd.DataFrame:
    n = 260
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    close = pd.Series(np.linspace(200, 100, n), index=idx)
    return pd.DataFrame({
        "open": close * 1.01, "high": close * 1.02,
        "low": close * 0.99, "close": close,
        "volume": pd.Series(np.full(n, 5_000_000.0), index=idx),
    })
