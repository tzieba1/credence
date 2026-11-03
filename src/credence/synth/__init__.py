"""Synthetic evaluation documents.

Certificates (and a few documents that are not certificates) rendered from a
specification, so the gold labels are known by construction. Some are
rasterised and degraded to stand in for scanned paper.
"""

from credence.synth.cases import CASES, CaseSpec
from credence.synth.fields import GOLD_KEYS, CertificateFields

__all__ = ["CASES", "GOLD_KEYS", "CaseSpec", "CertificateFields"]
