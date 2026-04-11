from __future__ import annotations

import pytest


def test_registry_find_code_only(registry):
    res = registry.check_okpd2("31.01.12")
    assert res.found is True
    assert res.exact_okpd_match is True
    assert res.matched_okpd2 == "31.01.12"
    assert res.is_parent_match is False
    assert res.reference_name == "Мебель деревянная для офисов"
    assert "Эталонное наименование" in res.message


def test_registry_name_mismatch(registry):
    res = registry.check_okpd2("31.01.12", "СТУЛ")
    assert res.found is True
    assert res.exact_okpd_match is True
    assert res.exact_name_match is False
    assert res.normalized_name_match is False
    assert res.reference_name == "Мебель деревянная для офисов"
    assert "но наименование отличается" in res.message.lower()


def test_registry_exact_name_match(registry):
    res = registry.check_okpd2("31.01.12", "Мебель деревянная для офисов")
    assert res.found is True
    assert res.exact_okpd_match is True
    assert res.exact_name_match is True or res.normalized_name_match is True
    assert "наименование совпадает" in res.message.lower()


def test_registry_normalized_name_match(registry):
    res = registry.check_okpd2("31.01.12", "мебель деревянная для офисов")
    assert res.found is True
    assert res.exact_okpd_match is True
    assert res.normalized_name_match is True
    assert "наименование совпадает" in res.message.lower()


def test_registry_parent_match_31_01_12_190(registry):
    res = registry.check_okpd2("31.01.12.190", "Мебель офисная деревянная прочая")
    assert res.found is True
    assert res.query_okpd2 == "31.01.12.190"
    assert res.matched_okpd2 == "31.01.12"
    assert res.is_parent_match is True
    assert res.reference_name == "Мебель деревянная для офисов"
    assert "родительский код 31.01.12" in res.message


def test_registry_parent_match_31_01_12_139(registry):
    res = registry.check_okpd2("31.01.12.139", "Шкафы деревянные прочие")
    assert res.found is True
    assert res.query_okpd2 == "31.01.12.139"
    assert res.matched_okpd2 == "31.01.12"
    assert res.is_parent_match is True
    assert res.reference_name == "Мебель деревянная для офисов"


def test_registry_not_found_keeps_full_code(registry):
    res = registry.check_okpd2("31.01.155.139")
    assert res.found is False
    assert res.query_okpd2 == "31.01.155.139"
    assert res.matched_okpd2 is None
    assert "31.01.155.139" in res.message
    assert "31.01.155" in res.message


def test_registry_invalid_code_raises(registry):
    with pytest.raises(ValueError):
        registry.check_okpd2("abc")


def test_find_okpd2_returns_rows(registry):
    rows = registry.find_okpd2("31.01.12")
    assert isinstance(rows, list)
    assert len(rows) >= 1
    assert rows[0]["okpd2"] == "31.01.12"