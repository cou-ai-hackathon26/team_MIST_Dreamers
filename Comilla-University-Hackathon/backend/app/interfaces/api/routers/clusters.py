"""POST /api/v1/admin/clusters/rebuild and GET /api/v1/admin/clusters (D2-T2, FR-ADM-03, 04, 05, SRS 8).

Both use the shared admin check `require_admin_token` from admin.py (session token or X-Admin-Token).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.application.ports.clustering import Cluster
from app.application.use_cases.clusters import ListClusters, RebuildClusters
from app.interfaces.api.deps import get_container
from app.interfaces.api.routers.admin import no_store, require_admin_token

router = APIRouter(
    prefix="/api/v1/admin", tags=["admin"], dependencies=[Depends(require_admin_token), Depends(no_store)]
)


class RebuildResponse(BaseModel):
    clusters: int
    questions: int
    labelled_by: str


class ClusterOut(BaseModel):
    id: int | None
    label: str
    size: int
    examples: list[str]

    @classmethod
    def of(cls, cluster: Cluster) -> "ClusterOut":
        return cls(id=cluster.id, label=cluster.label, size=cluster.size, examples=list(cluster.examples))


class ClustersResponse(BaseModel):
    clusters: list[ClusterOut]


def get_rebuild_clusters(request: Request) -> RebuildClusters:
    return get_container(request).rebuild_clusters


def get_list_clusters(request: Request) -> ListClusters:
    return get_container(request).list_clusters


@router.post("/clusters/rebuild", summary="Group all logged questions into topics (K-Means)")
def rebuild(use_case: Annotated[RebuildClusters, Depends(get_rebuild_clusters)]) -> RebuildResponse:
    result = use_case.execute()
    return RebuildResponse(
        clusters=result.clusters, questions=result.questions, labelled_by=result.labelled_by
    )


@router.get("/clusters", summary="Question topics with label, size and 3 examples")
def list_clusters(use_case: Annotated[ListClusters, Depends(get_list_clusters)]) -> ClustersResponse:
    return ClustersResponse(clusters=[ClusterOut.of(c) for c in use_case.execute()])
