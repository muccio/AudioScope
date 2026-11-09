"""Tests for MetadataEngine, BEXT, iXML, CART, and Artwork extraction."""

import struct
from src.core.metadata import MetadataEngine


def test_bext_parsing():
    desc = b"Master Sound Track".ljust(256, b"\x00")
    orig = b"AudioScope Studio".ljust(32, b"\x00")
    orig_ref = b"REF-001".ljust(32, b"\x00")
    orig_date = b"2026-11-09"
    orig_time = b"12:00:00"
    time_ref_low = 48000 * 60  # 1 minute at 48k
    time_ref_high = 0
    version = 1
    umid = b"\x00" * 64
    loudness_val = -2300  # -23.00 LUFS
    loudness_range = 750  # 7.50 LU
    max_tp = -150         # -1.50 dBTP
    max_mom = -1700
    max_st = -1850
    reserved = b"\x00" * 180
    coding_history = b"A=PCM,F=48000,W=24,M=stereo\r\n"

    bext_bytes = (
        desc + orig + orig_ref + orig_date + orig_time +
        struct.pack("<II", time_ref_low, time_ref_high) +
        struct.pack("<H", version) +
        umid +
        struct.pack("<hhhhh", loudness_val, loudness_range, max_tp, max_mom, max_st) +
        reserved + coding_history
    )

    bext = MetadataEngine.parse_bext_chunk(bext_bytes, sample_rate=48000)
    assert bext is not None
    assert bext.description == "Master Sound Track"
    assert bext.originator == "AudioScope Studio"
    assert bext.origination_date == "2026-11-09"
    assert bext.time_reference == 48000 * 60
    assert bext.timecode_start == "00:01:00:00"
    assert bext.loudness_value_lufs == -23.0
    assert bext.loudness_range_lu == 7.5
    assert bext.max_true_peak_dbtp == -1.5


def test_ixml_parsing():
    xml_content = b"""<?xml version="1.0" encoding="UTF-8"?>
    <BWFXML>
      <PROJECT>SciFi Odyssey</PROJECT>
      <SCENE>10</SCENE>
      <TAKE>4</TAKE>
      <CIRCLED>TRUE</CIRCLED>
      <NOTE>Clean dialogue take</NOTE>
      <TRACK_LIST>
        <TRACK>
          <CHANNEL_INDEX>1</CHANNEL_INDEX>
          <NAME>Boom</NAME>
          <FUNCTION>Dialogue</FUNCTION>
        </TRACK>
      </TRACK_LIST>
    </BWFXML>"""

    ixml = MetadataEngine.parse_ixml_chunk(xml_content)
    assert ixml is not None
    assert ixml.project == "SciFi Odyssey"
    assert ixml.scene == "10"
    assert ixml.take == "4"
    assert ixml.circled is True
    assert len(ixml.tracks) == 1
    assert ixml.tracks[0].name == "Boom"


def test_cart_parsing():
    version = b"0101"
    title = b"Morning News Jingle".ljust(64, b"\x00")
    artist = b"Station Orchestra".ljust(64, b"\x00")
    cut_id = b"CUT-12345".ljust(64, b"\x00")
    cart_bytes = version + title + artist + cut_id + (b"\x00" * 300)

    cart = MetadataEngine.parse_cart_chunk(cart_bytes)
    assert cart is not None
    assert cart.title == "Morning News Jingle"
    assert cart.artist == "Station Orchestra"
    assert cart.cut_id == "CUT-12345"
