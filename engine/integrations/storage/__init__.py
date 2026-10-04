"""Storage local de artefactos."""

from integrations.storage.base import FakeStorage, LocalStorage, ObjectStorage, build_storage

__all__ = ["FakeStorage", "LocalStorage", "ObjectStorage", "build_storage"]
