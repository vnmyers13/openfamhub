from fastapi import APIRouter

router = APIRouter()


@router.get("/events")
async def list_events():
    return {"events": []}


@router.post("/events")
async def create_event():
    return {"event": None}


@router.get("/events/{event_id}")
async def get_event(event_id: str):
    return {"event": None}


@router.patch("/events/{event_id}")
async def update_event(event_id: str):
    return {"event": None}


@router.delete("/events/{event_id}")
async def delete_event(event_id: str):
    return {"ok": True}


@router.get("/sources")
async def list_sources():
    return {"sources": []}


@router.post("/sources")
async def create_source():
    return {"source": None}


@router.patch("/sources/{source_id}")
async def update_source(source_id: str):
    return {"source": None}


@router.delete("/sources/{source_id}")
async def delete_source(source_id: str):
    return {"ok": True}


@router.post("/sources/{source_id}/sync")
async def sync_source(source_id: str):
    return {"ok": True}
