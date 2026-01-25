"""
Signal Serialization with Checksums for QUANT INDUSTRY
=======================================================
Provides secure serialization for trading signals with:
- Message integrity via checksums
- Versioned wire format
- Compact binary encoding
- Schema validation

Matches quant-platform pattern for inter-process communication.
"""

import hashlib
import hmac
import json
import logging
import struct
import time
import zlib
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, TypeVar, Union

logger = logging.getLogger(__name__)

T = TypeVar('T')


# ============== CONSTANTS ==============

MAGIC_BYTES = b'QSIG'  # Magic header for signal messages
FORMAT_VERSION = 1
CHECKSUM_ALGO = 'sha256'


# ============== EXCEPTIONS ==============

class SerializationError(Exception):
    """Base serialization error"""
    pass


class ChecksumError(SerializationError):
    """Checksum verification failed"""
    pass


class VersionMismatchError(SerializationError):
    """Unsupported format version"""
    pass


class SchemaError(SerializationError):
    """Schema validation failed"""
    pass


# ============== CHECKSUM UTILITIES ==============

def compute_checksum(data: bytes, algorithm: str = CHECKSUM_ALGO) -> str:
    """Compute checksum of data"""
    h = hashlib.new(algorithm)
    h.update(data)
    return h.hexdigest()


def compute_hmac(data: bytes, secret: bytes, algorithm: str = CHECKSUM_ALGO) -> str:
    """Compute HMAC of data with secret key"""
    h = hmac.new(secret, data, algorithm)
    return h.hexdigest()


def verify_checksum(data: bytes, expected: str, algorithm: str = CHECKSUM_ALGO) -> bool:
    """Verify checksum of data"""
    actual = compute_checksum(data, algorithm)
    return hmac.compare_digest(actual, expected)


# ============== SIGNAL TYPES ==============

class SignalDirection(Enum):
    """Trading signal direction"""
    LONG = "LONG"
    SHORT = "SHORT"
    HOLD = "HOLD"
    EXIT = "EXIT"


class SignalPriority(Enum):
    """Signal priority level"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


@dataclass
class TradingSignal:
    """
    Trading signal with full metadata.
    Designed for serialization and integrity verification.
    """
    # Identification
    id: str
    version: int = 1

    # Signal data
    symbol: str = ""
    direction: str = "HOLD"  # SignalDirection value
    confidence: float = 0.0
    strength: float = 0.0  # 0-100 scale

    # Pricing
    entry_price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    current_price: float = 0.0

    # Strategy info
    strategy: str = ""
    timeframe: str = "1H"
    regime: str = ""

    # Risk metrics
    risk_reward: float = 0.0
    position_size: float = 0.0
    max_risk: float = 0.0

    # Timing
    timestamp: str = ""
    expiry: str = ""
    priority: int = 2  # SignalPriority value

    # Metadata
    features: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Checksum (populated on serialization)
    checksum: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TradingSignal':
        """Create from dictionary"""
        # Filter to known fields
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)


# ============== SERIALIZER ==============

class SignalSerializer:
    """
    Serializes trading signals with integrity verification.

    Features:
    - JSON or binary encoding
    - Checksum verification
    - Optional compression
    - Optional encryption (with secret key)
    - Schema validation

    Example:
        serializer = SignalSerializer()

        # Serialize
        data = serializer.serialize(signal)

        # Deserialize with verification
        signal = serializer.deserialize(data)
    """

    def __init__(
        self,
        secret: bytes = None,
        compress: bool = True,
        binary: bool = False
    ):
        """
        Initialize serializer.

        Args:
            secret: Optional HMAC secret for signing
            compress: Whether to compress data
            binary: Use binary format (more compact)
        """
        self.secret = secret
        self.compress = compress
        self.binary = binary

    def serialize(
        self,
        signal: Union[TradingSignal, Dict[str, Any]],
        include_timestamp: bool = True
    ) -> bytes:
        """
        Serialize a signal to bytes.

        Args:
            signal: Signal to serialize
            include_timestamp: Include serialization timestamp

        Returns:
            Serialized bytes with checksum
        """
        # Convert to dict
        if isinstance(signal, TradingSignal):
            data = signal.to_dict()
        else:
            data = signal.copy()

        # Add timestamp
        if include_timestamp:
            data['_serialized_at'] = datetime.utcnow().isoformat()

        # Remove old checksum
        data.pop('checksum', None)

        # Encode to JSON
        json_bytes = json.dumps(data, sort_keys=True, default=str).encode('utf-8')

        # Compute checksum
        if self.secret:
            checksum = compute_hmac(json_bytes, self.secret)
        else:
            checksum = compute_checksum(json_bytes)

        # Add checksum to data
        data['checksum'] = checksum

        # Re-encode with checksum
        payload = json.dumps(data, sort_keys=True, default=str).encode('utf-8')

        # Compress if enabled
        if self.compress:
            payload = zlib.compress(payload)

        if self.binary:
            # Binary format with header
            return self._encode_binary(payload, checksum)
        else:
            # JSON format
            return payload

    def deserialize(
        self,
        data: bytes,
        verify: bool = True,
        signal_class: Type[T] = TradingSignal
    ) -> T:
        """
        Deserialize bytes to a signal.

        Args:
            data: Serialized bytes
            verify: Verify checksum
            signal_class: Class to deserialize into

        Returns:
            Deserialized signal

        Raises:
            ChecksumError: If verification fails
            SerializationError: If deserialization fails
        """
        try:
            # Check for binary format
            if data.startswith(MAGIC_BYTES):
                payload, stored_checksum = self._decode_binary(data)
            else:
                payload = data
                stored_checksum = None

            # Decompress if needed
            try:
                payload = zlib.decompress(payload)
            except zlib.error:
                # Not compressed
                pass

            # Parse JSON
            parsed = json.loads(payload.decode('utf-8'))

            # Verify checksum
            if verify:
                stored_checksum = stored_checksum or parsed.get('checksum', '')

                # Recompute checksum without the checksum field
                verify_data = parsed.copy()
                verify_data.pop('checksum', None)
                verify_bytes = json.dumps(verify_data, sort_keys=True, default=str).encode('utf-8')

                if self.secret:
                    expected = compute_hmac(verify_bytes, self.secret)
                else:
                    expected = compute_checksum(verify_bytes)

                if not hmac.compare_digest(stored_checksum, expected):
                    raise ChecksumError(
                        f"Checksum verification failed: expected {expected[:16]}..., "
                        f"got {stored_checksum[:16]}..."
                    )

            # Create signal object
            if signal_class == dict:
                return parsed
            elif hasattr(signal_class, 'from_dict'):
                return signal_class.from_dict(parsed)
            elif is_dataclass(signal_class):
                known_fields = {f.name for f in signal_class.__dataclass_fields__.values()}
                filtered = {k: v for k, v in parsed.items() if k in known_fields}
                return signal_class(**filtered)
            else:
                return signal_class(**parsed)

        except json.JSONDecodeError as e:
            raise SerializationError(f"Invalid JSON: {e}")
        except Exception as e:
            if isinstance(e, (ChecksumError, SerializationError)):
                raise
            raise SerializationError(f"Deserialization failed: {e}")

    def _encode_binary(self, payload: bytes, checksum: str) -> bytes:
        """
        Encode to binary format with header.

        Format:
        - 4 bytes: Magic (QSIG)
        - 1 byte: Version
        - 1 byte: Flags (bit 0: compressed)
        - 4 bytes: Payload length
        - 32 bytes: Checksum (SHA256)
        - N bytes: Payload
        """
        flags = 0x01 if self.compress else 0x00

        header = struct.pack(
            '>4sBBI32s',
            MAGIC_BYTES,
            FORMAT_VERSION,
            flags,
            len(payload),
            checksum.encode('utf-8')[:32].ljust(32, b'\x00')
        )

        return header + payload

    def _decode_binary(self, data: bytes) -> Tuple[bytes, str]:
        """
        Decode binary format.

        Returns:
            Tuple of (payload, checksum)
        """
        if len(data) < 42:  # Header size
            raise SerializationError("Data too short for binary format")

        magic, version, flags, payload_len, checksum_bytes = struct.unpack(
            '>4sBBI32s',
            data[:42]
        )

        if magic != MAGIC_BYTES:
            raise SerializationError(f"Invalid magic bytes: {magic}")

        if version != FORMAT_VERSION:
            raise VersionMismatchError(f"Unsupported version: {version}")

        payload = data[42:42 + payload_len]
        checksum = checksum_bytes.rstrip(b'\x00').decode('utf-8')

        return payload, checksum


# ============== BATCH SERIALIZATION ==============

@dataclass
class SignalBatch:
    """Batch of signals for efficient transfer"""
    signals: List[TradingSignal]
    batch_id: str = ""
    created_at: str = ""
    checksum: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "created_at": self.created_at,
            "signals": [s.to_dict() for s in self.signals],
            "count": len(self.signals),
            "checksum": self.checksum
        }


class BatchSerializer:
    """
    Serializer for signal batches.

    More efficient than serializing individual signals.
    """

    def __init__(self, secret: bytes = None):
        self.secret = secret
        self._serializer = SignalSerializer(secret=secret, compress=True)

    def serialize_batch(
        self,
        signals: List[TradingSignal],
        batch_id: str = None
    ) -> bytes:
        """Serialize a batch of signals"""
        import uuid

        batch = SignalBatch(
            signals=signals,
            batch_id=batch_id or str(uuid.uuid4())[:8],
            created_at=datetime.utcnow().isoformat()
        )

        return self._serializer.serialize(batch.to_dict())

    def deserialize_batch(
        self,
        data: bytes,
        verify: bool = True
    ) -> SignalBatch:
        """Deserialize a batch of signals"""
        parsed = self._serializer.deserialize(data, verify=verify, signal_class=dict)

        signals = [
            TradingSignal.from_dict(s)
            for s in parsed.get('signals', [])
        ]

        return SignalBatch(
            signals=signals,
            batch_id=parsed.get('batch_id', ''),
            created_at=parsed.get('created_at', ''),
            checksum=parsed.get('checksum', '')
        )


# ============== SCHEMA VALIDATION ==============

@dataclass
class FieldSchema:
    """Schema for a single field"""
    name: str
    type: type
    required: bool = False
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    allowed_values: Optional[List[Any]] = None
    validator: Optional[Callable[[Any], bool]] = None


class SignalSchema:
    """
    Schema validator for trading signals.

    Ensures signals meet data quality requirements.
    """

    STANDARD_SCHEMA = [
        FieldSchema("id", str, required=True),
        FieldSchema("symbol", str, required=True),
        FieldSchema("direction", str, required=True,
                    allowed_values=["LONG", "SHORT", "HOLD", "EXIT"]),
        FieldSchema("confidence", float, required=True, min_value=0.0, max_value=1.0),
        FieldSchema("entry_price", float, min_value=0.0),
        FieldSchema("stop_loss", float, min_value=0.0),
        FieldSchema("take_profit", float, min_value=0.0),
        FieldSchema("strategy", str),
        FieldSchema("timestamp", str, required=True),
    ]

    def __init__(self, fields: List[FieldSchema] = None):
        self.fields = fields or self.STANDARD_SCHEMA
        self._field_map = {f.name: f for f in self.fields}

    def validate(
        self,
        signal: Union[TradingSignal, Dict[str, Any]]
    ) -> Tuple[bool, List[str]]:
        """
        Validate a signal against the schema.

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        if isinstance(signal, TradingSignal):
            data = signal.to_dict()
        else:
            data = signal

        for field in self.fields:
            value = data.get(field.name)

            # Check required
            if field.required and (value is None or value == ""):
                errors.append(f"Missing required field: {field.name}")
                continue

            if value is None:
                continue

            # Check type
            if not isinstance(value, field.type):
                try:
                    # Try conversion
                    value = field.type(value)
                except (ValueError, TypeError):
                    errors.append(
                        f"Invalid type for {field.name}: expected {field.type.__name__}"
                    )
                    continue

            # Check range
            if field.min_value is not None and value < field.min_value:
                errors.append(
                    f"{field.name} below minimum: {value} < {field.min_value}"
                )

            if field.max_value is not None and value > field.max_value:
                errors.append(
                    f"{field.name} above maximum: {value} > {field.max_value}"
                )

            # Check allowed values
            if field.allowed_values and value not in field.allowed_values:
                errors.append(
                    f"Invalid value for {field.name}: {value} not in {field.allowed_values}"
                )

            # Custom validator
            if field.validator and not field.validator(value):
                errors.append(f"Validation failed for {field.name}")

        return len(errors) == 0, errors

    def validate_or_raise(
        self,
        signal: Union[TradingSignal, Dict[str, Any]]
    ) -> None:
        """Validate and raise on error"""
        is_valid, errors = self.validate(signal)
        if not is_valid:
            raise SchemaError(f"Schema validation failed: {errors}")


# ============== UTILITIES ==============

def create_signal_id() -> str:
    """Create a unique signal ID"""
    import uuid
    timestamp = int(time.time() * 1000)
    unique = uuid.uuid4().hex[:8]
    return f"sig_{timestamp}_{unique}"


def hash_signal(signal: Union[TradingSignal, Dict[str, Any]]) -> str:
    """
    Create a content hash for a signal.
    Useful for deduplication.
    """
    if isinstance(signal, TradingSignal):
        data = signal.to_dict()
    else:
        data = signal.copy()

    # Remove non-content fields
    for key in ['id', 'timestamp', 'checksum', '_serialized_at']:
        data.pop(key, None)

    json_bytes = json.dumps(data, sort_keys=True, default=str).encode('utf-8')
    return compute_checksum(json_bytes)[:16]
