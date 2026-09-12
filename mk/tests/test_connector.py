"""Tests for the native TimeNet Penmanshiel and Kelmarsh connectors and metadata."""

from pathlib import Path
from fractions import Fraction
import pytest

from src.connectors.kelmarsh.connector import KelmarshConnector
from src.connectors.penmanshiel.connector import PenmanshielConnector
from src.data.schemas import (
    KELMARSH_DATASET_ID,
    PENMANSHIEL_DATASET_ID,
    SELECTED_SIGNALS,
    WINDOW_STEPS,
)
from timenet.types import DatasetMetadata, License, Domain


def test_penmanshiel_connector_metadata():
    connector = PenmanshielConnector()
    meta = connector.metadata()
    assert isinstance(meta, DatasetMetadata)
    assert meta.dataset_id == PENMANSHIEL_DATASET_ID
    assert "Penmanshiel" in meta.name
    assert meta.license == License.CC_BY_4_0
    assert Domain.ENERGY in meta.domains


def test_penmanshiel_connector_download_and_convert(tmp_path):
    connector = PenmanshielConnector()
    cache_dir = tmp_path / "cache"
    refs = connector.download(cache_dir)
    assert len(refs) == 1
    assert refs[0].exists()

    dataset = connector.convert(refs)
    assert len(dataset.records) > 0
    assert len(dataset.tasks) > 0

    first_record = dataset.records[0]
    assert len(first_record.time_series) == len(SELECTED_SIGNALS)
    assert first_record.time_series[0].n_values == WINDOW_STEPS


def test_kelmarsh_connector_metadata():
    connector = KelmarshConnector()
    meta = connector.metadata()
    assert isinstance(meta, DatasetMetadata)
    assert meta.dataset_id == KELMARSH_DATASET_ID
    assert "Kelmarsh" in meta.name
    assert meta.license == License.CC_BY_4_0
    assert Domain.ENERGY in meta.domains


def test_kelmarsh_connector_download_and_convert(tmp_path):
    connector = KelmarshConnector()
    cache_dir = tmp_path / "cache_kelmarsh"
    refs = connector.download(cache_dir)
    assert len(refs) == 1
    assert refs[0].exists()

    dataset = connector.convert(refs)
    assert len(dataset.records) > 0
    assert len(dataset.tasks) > 0
