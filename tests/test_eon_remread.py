# Unit tests for EON Remote Read integration (eon_remread)

from datetime import datetime, timezone

import pytest

from custom_components.eon_remread.eon_remread import EonEnergyData


@pytest.fixture
def eon():
    """EonEnergyData instance without HA, for testing parse/aggregation logic."""
    return EonEnergyData(username="test@test.com", password="secret", pod="POD1")


class TestParseTimestamp:
    """Tests for _parse_timestamp."""

    def test_valid_date_format(self, eon):
        # 1706832000000 ms = 2024-02-02 00:00:00 UTC
        result = eon._parse_timestamp("/Date(1706832000000)/")
        assert result is not None
        assert result.year == 2024
        assert result.month == 2
        assert result.day == 2
        assert result.hour == 0
        assert result.minute == 0
        assert result.tzinfo == timezone.utc

    def test_epoch_zero(self, eon):
        result = eon._parse_timestamp("/Date(0)/")
        assert result == datetime(1970, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    def test_invalid_string_returns_none(self, eon):
        assert eon._parse_timestamp("invalid") is None
        assert eon._parse_timestamp("") is None
        assert eon._parse_timestamp("/Date()/") is None
        assert eon._parse_timestamp("2024-01-01T00:00:00") is None


class TestParseEnergyData:
    """Tests for _parse_energy_data (totals from API response)."""

    def test_empty_data(self, eon):
        assert eon._parse_energy_data({}) == (0.0, 0.0)
        assert eon._parse_energy_data({"d": {}}) == (0.0, 0.0)
        assert eon._parse_energy_data({"d": {"MeasDatas": {}}}) == (0.0, 0.0)
        assert eon._parse_energy_data({"d": {"MeasDatas": {"results": []}}}) == (0.0, 0.0)

    def test_single_entry(self, eon):
        data = {
            "d": {
                "MeasDatas": {
                    "results": [{"Num1": 10.5, "Num2": 3.2}]
                }
            }
        }
        assert eon._parse_energy_data(data) == (10.5, 3.2)

    def test_multiple_entries_summed(self, eon):
        data = {
            "d": {
                "MeasDatas": {
                    "results": [
                        {"Num1": 1.0, "Num2": 0.5},
                        {"Num1": 2.0, "Num2": 1.0},
                        {"Num1": 0.5, "Num2": 0.0},
                    ]
                }
            }
        }
        assert eon._parse_energy_data(data) == (3.5, 1.5)

    def test_missing_or_none_num1_num2_treated_as_zero(self, eon):
        data = {
            "d": {
                "MeasDatas": {
                    "results": [
                        {"Num1": 5, "Num2": None},
                        {"Num2": 5},
                        {"Num1": None, "Num2": 0},
                    ]
                }
            }
        }
        assert eon._parse_energy_data(data) == (5.0, 5.0)


class TestParseEnergyDataTimeseries:
    """Tests for _parse_energy_data_timeseries."""

    def test_empty_results(self, eon):
        data = {"d": {"MeasDatas": {"results": []}}}
        assert eon._parse_energy_data_timeseries(data) == []

    def test_single_point_with_timestamp(self, eon):
        data = {
            "d": {
                "MeasDatas": {
                    "results": [
                        {
                            "Timestamp": "/Date(1706832000000)/",
                            "Num1": 1.0,
                            "Num2": 0.5,
                        }
                    ]
                }
            }
        }
        out = eon._parse_energy_data_timeseries(data)
        assert len(out) == 1
        dt, num1, num2, num3, num4 = out[0]
        assert dt == datetime(2024, 2, 2, 0, 0, 0, tzinfo=timezone.utc)
        assert num1 == 1.0
        assert num2 == 0.5
        assert num3 is None
        assert num4 is None

    def test_datum_fallback(self, eon):
        """If Timestamp is missing, Datum is used."""
        data = {
            "d": {
                "MeasDatas": {
                    "results": [
                        {
                            "Datum": "/Date(1706832000000)/",
                            "Num1": 1.0,
                            "Num2": 0.0,
                        }
                    ]
                }
            }
        }
        out = eon._parse_energy_data_timeseries(data)
        assert len(out) == 1
        assert out[0][0] == datetime(2024, 2, 2, 0, 0, 0, tzinfo=timezone.utc)

    def test_skips_entry_without_valid_timestamp(self, eon):
        data = {
            "d": {
                "MeasDatas": {
                    "results": [
                        {"Timestamp": "/Date(1706832000000)/", "Num1": 1, "Num2": 0},
                        {"Timestamp": "invalid", "Num1": 99, "Num2": 99},
                        {"Num1": 2, "Num2": 0},
                    ]
                }
            }
        }
        out = eon._parse_energy_data_timeseries(data)
        assert len(out) == 1
        assert out[0][1] == 1.0

    def test_num3_num4_preserved_when_positive(self, eon):
        data = {
            "d": {
                "MeasDatas": {
                    "results": [
                        {
                            "Timestamp": "/Date(1706832000000)/",
                            "Num1": 1.0,
                            "Num2": 0.5,
                            "Num3": 100.0,
                            "Num4": 50.0,
                        }
                    ]
                }
            }
        }
        out = eon._parse_energy_data_timeseries(data)
        assert len(out) == 1
        _, _, _, num3, num4 = out[0]
        assert num3 == 100.0
        assert num4 == 50.0

    def test_num3_num4_set_to_none_when_zero_or_negative(self, eon):
        data = {
            "d": {
                "MeasDatas": {
                    "results": [
                        {
                            "Timestamp": "/Date(1706832000000)/",
                            "Num1": 1,
                            "Num2": 1,
                            "Num3": 0,
                            "Num4": -1,
                        }
                    ]
                }
            }
        }
        out = eon._parse_energy_data_timeseries(data)
        assert len(out) == 1
        assert out[0][3] is None
        assert out[0][4] is None

    def test_num3_num4_empty_string_treated_as_none(self, eon):
        data = {
            "d": {
                "MeasDatas": {
                    "results": [
                        {
                            "Timestamp": "/Date(1706832000000)/",
                            "Num1": 1,
                            "Num2": 1,
                            "Num3": "",
                            "Num4": "",
                        }
                    ]
                }
            }
        }
        out = eon._parse_energy_data_timeseries(data)
        assert out[0][3] is None
        assert out[0][4] is None


class TestBuildHourlyCumulative:
    """Tests for _build_hourly_cumulative."""

    def test_empty_timeseries(self, eon):
        import_list, export_list = eon._build_hourly_cumulative([])
        assert import_list == []
        assert export_list == []

    def test_single_hour_without_num3_num4(self, eon):
        # One 15-min point: use num1/num2 as cumulative for that hour
        base = datetime(2024, 2, 2, 10, 0, 0, tzinfo=timezone.utc)
        timeseries = [(base, 2.0, 1.0, None, None)]
        import_list, export_list = eon._build_hourly_cumulative(timeseries)
        assert len(import_list) == 1
        assert len(export_list) == 1
        assert import_list[0] == (base, 2.0)
        assert export_list[0] == (base, 1.0)

    def test_two_hours_cumulative_without_num3_num4(self, eon):
        base1 = datetime(2024, 2, 2, 10, 0, 0, tzinfo=timezone.utc)
        base2 = datetime(2024, 2, 2, 11, 0, 0, tzinfo=timezone.utc)
        timeseries = [
            (base1, 1.0, 0.5, None, None),
            (base2, 2.0, 1.0, None, None),
        ]
        import_list, export_list = eon._build_hourly_cumulative(timeseries)
        assert len(import_list) == 2
        assert import_list[0] == (base1, 1.0)
        assert import_list[1] == (base2, 3.0)
        assert export_list[0] == (base1, 0.5)
        assert export_list[1] == (base2, 1.5)

    def test_single_hour_with_num3_num4_used_as_cumulative(self, eon):
        base = datetime(2024, 2, 2, 10, 0, 0, tzinfo=timezone.utc)
        timeseries = [(base, 0.5, 0.25, 100.0, 50.0)]
        import_list, export_list = eon._build_hourly_cumulative(timeseries)
        assert import_list[0] == (base, 100.0)
        assert export_list[0] == (base, 50.0)

    def test_four_quarters_in_same_hour_accumulate_num1_num2(self, eon):
        base = datetime(2024, 2, 2, 10, 0, 0, tzinfo=timezone.utc)
        timeseries = [
            (base.replace(minute=0), 1.0, 0.5, None, None),
            (base.replace(minute=15), 1.0, 0.5, None, None),
            (base.replace(minute=30), 1.0, 0.5, None, None),
            (base.replace(minute=45), 1.0, 0.5, None, None),
        ]
        import_list, export_list = eon._build_hourly_cumulative(timeseries)
        assert len(import_list) == 1
        assert import_list[0] == (base, 4.0)
        assert export_list[0] == (base, 2.0)

    def test_last_num3_num4_in_hour_used(self, eon):
        """When multiple points in same hour have Num3/Num4, last one wins."""
        base = datetime(2024, 2, 2, 10, 0, 0, tzinfo=timezone.utc)
        timeseries = [
            (base.replace(minute=0), 1.0, 0.5, 10.0, 5.0),
            (base.replace(minute=30), 1.0, 0.5, 20.0, 10.0),
        ]
        import_list, export_list = eon._build_hourly_cumulative(timeseries)
        assert len(import_list) == 1
        assert import_list[0] == (base, 20.0)
        assert export_list[0] == (base, 10.0)

    def test_values_rounded_to_three_decimals(self, eon):
        base = datetime(2024, 2, 2, 10, 0, 0, tzinfo=timezone.utc)
        timeseries = [(base, 1.11114, 2.22226, None, None)]
        import_list, export_list = eon._build_hourly_cumulative(timeseries)
        assert import_list[0][1] == 1.111
        assert export_list[0][1] == 2.222


class TestGetters:
    """Tests for get_total_import, get_total_export, get_last_updated."""

    def test_initial_values(self, eon):
        assert eon.get_total_import() == 0.0
        assert eon.get_total_export() == 0.0
        assert eon.get_last_updated() is None

    def test_after_manual_assign(self, eon):
        eon.total_import = 10.5
        eon.total_export = 3.2
        eon.last_updated = datetime(2024, 2, 2)
        assert eon.get_total_import() == 10.5
        assert eon.get_total_export() == 3.2
        assert eon.get_last_updated() == datetime(2024, 2, 2)
