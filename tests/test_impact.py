from eaglesignal.analysis.impact import map_impacts
from eaglesignal.ingestion.government import GovEvent, GovSnapshot
from eaglesignal.schemas import AssetEntity, AssetType


def _gov():
    return GovSnapshot(
        available=True,
        providers=["openfda", "doj_ftc", "gdelt_policy"],
        events=[
            GovEvent(title="Class II recall — ENDO USA, Inc.: particulate matter", source="FDA Drug Recall", url="", kind="fda"),
            GovEvent(title="FTC: Microsoft Corporation merger review consent order", source="FTC", url="", kind="antitrust"),
            GovEvent(title="New export control rules target semiconductor equipment", source="Federal Register", url="", kind="policy"),
            GovEvent(title="FTC: 1010 Digital Works LLC; Analysis of Proposed Consent Order", source="FTC", url="", kind="antitrust"),
        ],
    )


def test_direct_company_match():
    msft = AssetEntity(ticker="MSFT", asset_type=AssetType.equity,
                       company_name="Microsoft Corporation", strategy_tags=["technology", "ai", "cloud"])
    impacts = map_impacts(msft, _gov())
    kinds = {i.match_kind for i in impacts}
    assert "direct" in kinds
    direct = [i for i in impacts if i.match_kind == "direct"]
    assert any("Microsoft" in i.event.title for i in direct)
    # Direct antitrust action carries an adverse polarity.
    assert all(i.polarity <= 0 for i in direct)


def test_no_overbroad_unrelated_actions():
    msft = AssetEntity(ticker="MSFT", asset_type=AssetType.equity,
                       company_name="Microsoft Corporation", strategy_tags=["technology", "ai", "cloud"])
    impacts = map_impacts(msft, _gov())
    titles = [i.event.title for i in impacts]
    # Unrelated FDA recall and unrelated FTC consent order must NOT attach to MSFT.
    assert not any("ENDO USA" in t for t in titles)
    assert not any("1010 Digital Works" in t for t in titles)


def test_thematic_sector_match():
    nvda = AssetEntity(ticker="NVDA", asset_type=AssetType.equity,
                       company_name="NVIDIA Corporation", strategy_tags=["ai", "semiconductors"])
    impacts = map_impacts(nvda, _gov())
    # The semiconductor export-control policy headline should attach thematically.
    assert any(i.match_kind.startswith("thematic") for i in impacts)
    thematic = [i for i in impacts if i.match_kind.startswith("thematic")]
    assert all(i.polarity == 0.0 for i in thematic)  # context only, no directional bias


def test_unavailable_gov_returns_empty():
    aapl = AssetEntity(ticker="AAPL", asset_type=AssetType.equity, company_name="Apple Inc.")
    assert map_impacts(aapl, GovSnapshot(available=False)) == []
