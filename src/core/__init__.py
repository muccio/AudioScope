"""AudioScope Core Engine Modules."""

from src.core.decoder import UniversalAudioDecoder, StreamInfo, samples_to_timecode
from src.core.metadata import (
    MetadataEngine,
    FileMetadata,
    BextMetadata,
    IXMLMetadata,
    CartMetadata,
    EmbeddedArtwork,
)
from src.core.analyzer import AudioAnalyzer, AudioMetrics, ComplianceItem
from src.core.hex_reader import HexReader, ContainerChunkParser, ChunkNode

__all__ = [
    "UniversalAudioDecoder",
    "StreamInfo",
    "samples_to_timecode",
    "MetadataEngine",
    "FileMetadata",
    "BextMetadata",
    "IXMLMetadata",
    "CartMetadata",
    "EmbeddedArtwork",
    "AudioAnalyzer",
    "AudioMetrics",
    "ComplianceItem",
    "HexReader",
    "ContainerChunkParser",
    "ChunkNode",
]
