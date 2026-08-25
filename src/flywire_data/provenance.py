"""Immutable descriptions of the upstream data sources.

Every number, URL, checksum and version string in this module was read from the
official record (Zenodo REST API / GitHub REST API) and not from memory. If you
change a version here, re-verify the checksum against the upstream record.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

# --------------------------------------------------------------------------- #
# Connectivity: FlyWire whole-brain connectome, snapshot v783
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ConnectivitySource:
    """The Zenodo deposit holding the FlyWire v783 proofread edge list."""

    zenodo_record: str = "10676866"
    doi: str = "10.5281/zenodo.10676866"
    concept_doi: str = "10.5281/zenodo.10676865"
    title: str = "FlyWire Whole-brain Connectome Connectivity Data"
    version: str = "783.0"
    publication_date: str = "2024-06-02"
    license: str = "CC-BY-4.0"
    filename: str = "proofread_connections_783.feather"
    size_bytes: int = 852_022_274
    md5: str = "f48f972d262323a102aed49af1396b8a"

    @property
    def url(self) -> str:
        return (
            f"https://zenodo.org/records/{self.zenodo_record}"
            f"/files/{self.filename}?download=1"
        )

    @property
    def record_url(self) -> str:
        return f"https://zenodo.org/records/{self.zenodo_record}"


CONNECTIVITY = ConnectivitySource()


# --------------------------------------------------------------------------- #
# Annotations: Schlegel et al. cell typing of the FlyWire 783 release
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class AnnotationRelease:
    """One tagged release of ``flyconnectome/flywire_annotations``."""

    tag: str
    published_at: str
    md5: str
    #: Column that carries the fine-grained cell type in this release.
    #: In v2.x the central-complex types live in ``hemibrain_type`` (transferred
    #: from the hemibrain); from v3.0.0 they were promoted into ``cell_type``.
    type_columns: tuple[str, ...]
    reference: str

    repo: str = "flyconnectome/flywire_annotations"
    path: str = "supplemental_files/Supplemental_file1_neuron_annotations.tsv"

    @property
    def url(self) -> str:
        return f"https://raw.githubusercontent.com/{self.repo}/{self.tag}/{self.path}"

    @property
    def release_url(self) -> str:
        return f"https://github.com/{self.repo}/releases/tag/{self.tag}"

    @property
    def cache_name(self) -> str:
        return f"neuron_annotations_{self.tag}.tsv"


ANNOTATION_RELEASES: Mapping[str, AnnotationRelease] = {
    "v2.1.0": AnnotationRelease(
        tag="v2.1.0",
        published_at="2024-07-30",
        md5="8527e0a95ed5f112766b13260a91e8e2",
        # cell_type first, hemibrain_type as fallback: in v2.1.0 the CX types we
        # want are only present in hemibrain_type.
        type_columns=("cell_type", "hemibrain_type"),
        reference=(
            "Schlegel, P., Yin, Y., Bates, A.S. et al. Whole-brain annotation and "
            "multi-connectome cell typing of Drosophila. Nature 634, 139-152 (2024). "
            "https://doi.org/10.1038/s41586-024-07686-5"
        ),
    ),
    "v3.1.0": AnnotationRelease(
        tag="v3.1.0",
        published_at="2026-07-21",
        md5="719904abad876c68ace1b5690c9b9b63",
        type_columns=("cell_type", "hemibrain_type"),
        reference=(
            "Berg et al., updated FlyWire annotations matching MaleCNS v1.0 "
            "(Cell, accepted in principle). Release notes: "
            "https://github.com/flyconnectome/flywire_annotations/releases/tag/v3.1.0"
        ),
    ),
}

#: Default annotation release. v2.1.0 is the version *reported on* in Schlegel
#: et al. (2024) and Dorkenwald et al. (2024) -- the same papers that describe
#: the v783 connectivity snapshot -- so it is the most directly citable pairing.
DEFAULT_ANNOTATION_VERSION = "v2.1.0"


# --------------------------------------------------------------------------- #
# Licensing / citation
# --------------------------------------------------------------------------- #

LICENSE_NOTES: tuple[str, ...] = (
    "Connectivity dump (Zenodo 10.5281/zenodo.10676866): CC-BY-4.0, as declared "
    "in the Zenodo record metadata.",
    "FlyWire community proofreading and annotations: the FlyWire Terms of Service "
    "(https://flywire.ai/tos) state that edits and annotations 'will be made freely "
    "available under a CC-BY-NC 4.0 license'. The stricter non-commercial clause "
    "therefore governs any derived product that embeds the annotations.",
)

CITATIONS: tuple[str, ...] = (
    "Dorkenwald, S., Matsliah, A., Sterling, A.R. et al. Neuronal wiring diagram of "
    "an adult brain. Nature 634, 124-138 (2024). "
    "https://doi.org/10.1038/s41586-024-07558-y",
    "Schlegel, P., Yin, Y., Bates, A.S. et al. Whole-brain annotation and "
    "multi-connectome cell typing of Drosophila. Nature 634, 139-152 (2024). "
    "https://doi.org/10.1038/s41586-024-07686-5",
    "Eckstein, N., Bates, A.S., Champion, A. et al. Neurotransmitter classification "
    "from electron microscopy images at synaptic sites in Drosophila melanogaster. "
    "Cell 187, 2574-2594 (2024). https://doi.org/10.1016/j.cell.2024.03.016",
    "Buhmann, J., Sheridan, A., Malin-Mayor, C. et al. Automatic detection of "
    "synaptic partners in a whole-brain Drosophila electron microscopy data set. "
    "Nature Methods 18, 771-774 (2021). https://doi.org/10.1038/s41592-021-01183-7",
)
