"""Lossless bounded-size storage for the unchanged primitive pair stream."""
import gzip
import hashlib
import json
from ic_evidence_json import loads as json_loads
from pathlib import Path

from ic_coherent_feedback import spec_digest
from ic_schedule_audit import ScheduleTrace


FORMAT = "IC-PAIR-SHARDS-1"
PAIR = "IC-PAIR-U32LE-1"
SHARD_BYTES = 48 * 1024 * 1024
BLOCK = 1024 * 1024


def pack_trace(path, summary, *, shard_bytes=SHARD_BYTES):
    """Replace a flat trace with its lossless manifest only after verification."""
    path = Path(path)
    if type(shard_bytes) is not int or shard_bytes < 8 or shard_bytes % 8:
        raise ValueError("trace shard size must be a positive whole number of pair records")
    shards, total, overall = [], 0, hashlib.sha256()
    with gzip.open(path, "rb") as source:
        header_line = source.readline()
        header = json_loads(header_line)
        if header.get("format") != PAIR:
            raise ValueError("only an original primitive pair stream can be sharded")
        pending = source.read(min(BLOCK, shard_bytes))
        while pending:
            index = len(shards) + 1
            destination = path.with_name(path.stem + f".part-{index:04d}.gz")
            digest, size = hashlib.sha256(), 0
            with destination.open("wb") as raw_file:
                with gzip.GzipFile(filename="", mode="wb", fileobj=raw_file, mtime=0, compresslevel=6) as output:
                    output.write(header_line)
                    while pending:
                        if len(pending) % 8:
                            raise ValueError("truncated primitive pair record before sharding")
                        output.write(pending)
                        digest.update(pending)
                        overall.update(pending)
                        size += len(pending)
                        if size == shard_bytes:
                            break
                        pending = source.read(min(BLOCK, shard_bytes - size))
            records = size // 8
            shards.append({"file": destination.name, "records": records,
                           "sha256_of_pair_records": digest.hexdigest(),
                           "compressed_file_sha256": hashlib.sha256(destination.read_bytes()).hexdigest()})
            total += records
            pending = source.read(min(BLOCK, shard_bytes)) if size == shard_bytes else b""
    actual = {"format": PAIR, "steps": total, "sha256_of_pair_records": overall.hexdigest()}
    if actual != summary:
        raise ValueError("sharding differs from the independently counted primitive stream")
    if not shards:
        return summary
    manifest = {"format": FORMAT, "metadata": header, "trace": summary, "shards": shards}
    temporary = path.with_name(path.name + ".manifest.tmp")
    with temporary.open("wb") as raw_file:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw_file, mtime=0, compresslevel=6) as output:
            output.write((json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n").encode())
    temporary.replace(path)
    return {**summary, "storage_manifest_sha256": spec_digest(manifest)}


class _ShardReader:
    def __init__(self, path, manifest):
        if set(manifest) != {"format", "metadata", "trace", "shards"} or not manifest["shards"]:
            raise ValueError("invalid primitive trace shard manifest")
        self.base, self.manifest = Path(path).parent, manifest
        self.parts, self.index, self.stream = manifest["shards"], 0, None
        self.header = (json.dumps(manifest["metadata"], sort_keys=True) + "\n").encode()
        self.header_read = False
        names = []
        for entry in self.parts:
            if set(entry) != {"file", "records", "sha256_of_pair_records", "compressed_file_sha256"}:
                raise ValueError("invalid primitive trace shard fields")
            name = entry["file"]
            if not isinstance(name, str) or "/" in name or "\\" in name or ":" in name or name in (".", ".."):
                raise ValueError("trace shard must name a local sibling file")
            if type(entry["records"]) is not int or entry["records"] <= 0:
                raise ValueError("trace shards need positive record counts")
            names.append(name)
        if len(names) != len(set(names)) or sum(p["records"] for p in self.parts) != manifest["trace"]["steps"]:
            raise ValueError("duplicate or inconsistent primitive trace shards")

    def readline(self):
        if self.header_read:
            raise ValueError("primitive shard stream has only one metadata header")
        self.header_read = True
        return self.header

    def _open(self):
        if self.index >= len(self.parts):
            return False
        entry = self.parts[self.index]
        path = self.base / entry["file"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["compressed_file_sha256"]:
            raise ValueError("primitive trace shard compressed-file digest mismatch")
        self.stream = gzip.open(path, "rb")
        try:
            if json_loads(self.stream.readline()) != self.manifest["metadata"]:
                raise ValueError("primitive trace shard metadata mismatch")
        except BaseException:
            self.stream.close()
            self.stream = None
            raise
        self.digest, self.bytes = hashlib.sha256(), 0
        return True

    def read(self, size=-1):
        chunks, remaining = [], size
        while remaining != 0:
            if self.stream is None and not self._open():
                break
            data = self.stream.read(remaining)
            if data:
                chunks.append(data)
                self.digest.update(data)
                self.bytes += len(data)
                if size >= 0:
                    remaining -= len(data)
                continue
            entry = self.parts[self.index]
            self.stream.close()
            self.stream = None
            if self.bytes != entry["records"] * 8 or self.digest.hexdigest() != entry["sha256_of_pair_records"]:
                raise ValueError("primitive trace shard record-count or raw digest mismatch")
            self.index += 1
        return b"".join(chunks)

    def close(self):
        if self.stream is not None:
            self.stream.close()


class M6Trace(ScheduleTrace):
    """Original strict pair replay, transparently reading lossless shards."""
    def __init__(self, path, metadata, replay=False):
        self.path, self.manifest = Path(path), None
        if replay:
            with gzip.open(path, "rb") as probe:
                header = json_loads(probe.readline())
                if header.get("format") == FORMAT:
                    if probe.read(1):
                        raise ValueError("unaccounted trace manifest data")
                    self.manifest = header
            if self.manifest is not None:
                self.replay, self.count, self.digest = True, 0, hashlib.sha256()
                self.stream = _ShardReader(path, self.manifest)
                if json_loads(self.stream.readline()) != {"format": PAIR, **metadata}:
                    raise ValueError("primitive trace shard binding mismatch")
                return
        super().__init__(path, metadata, replay=replay)

    def close(self):
        result = super().close()
        if self.replay and self.manifest is not None:
            if result != self.manifest["trace"]:
                raise ValueError("whole primitive shard stream summary mismatch")
            return {**result, "storage_manifest_sha256": spec_digest(self.manifest)}
        if not self.replay and self.path.stat().st_size > SHARD_BYTES:
            return pack_trace(self.path, result)
        return result
