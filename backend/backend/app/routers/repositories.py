import json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.config import get_settings
from app.rate_limit import client_ip, limiter
from app.security import safe_repo_path
from app.services.chat import answer_question, fallback_answer, prepare_chat
from app.services.llm import LLMProvider
from app.services.store import (
    add_message,
    delete_chat,
    get_chat,
    get_file,
    get_repository,
    list_chats,
    list_files,
    list_repositories,
)

router = APIRouter()


class ChatRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1500)
    chat_id: str | None = None
    stream: bool = False


def _repo_or_404(repo: dict | None):
    if not repo:
        raise HTTPException(status_code=404, detail="Repository analysis not found.")
    return repo


@router.get("/api/v1/repositories")
async def repositories():
    return {"items": await list_repositories()}


@router.get("/api/v1/repositories/{repository_id}")
async def repository(repository_id: str):
    repo = _repo_or_404(await get_repository(repository_id))
    files = await list_files(repository_id)
    return {
        "id": repo["id"],
        "repository": {
            "id": repo["id"],
            "owner": repo["owner"],
            "name": repo["name"],
            "full_name": repo["full_name"],
            "description": repo["description"],
            "homepage": repo["homepage"],
            "html_url": repo["html_url"],
            "default_branch": repo["default_branch"],
            "commit_sha": repo["commit_sha"],
            "language": repo["language"],
            "languages": repo["languages"],
            "stars": repo["stars"],
            "forks": repo["forks"],
            "open_issues": repo["open_issues"],
            "license": repo["license"],
            "created_at": repo["github_created_at"],
            "updated_at": repo["github_updated_at"],
            "size": repo["size"],
            "topics": repo["topics"],
            "visibility": repo["visibility"],
            "archived": repo["archived"],
            "source": "github_api",
        },
        "stats": repo["stats"],
        "tree": repo["tree"],
        "files": files,
        "report": repo["analysis"],
        "index_status": repo["index_status"],
        "embedding_model": repo["embedding_model"],
        "cached": True,
    }


@router.get("/api/v1/repositories/{repository_id}/tree")
async def repository_tree(repository_id: str):
    repo = _repo_or_404(await get_repository(repository_id))
    return {"tree": repo["tree"], "truncated": bool((repo.get("stats") or {}).get("tree_truncated"))}


@router.get("/api/v1/repositories/{repository_id}/files")
async def repository_file(repository_id: str, path: str):
    _repo_or_404(await get_repository(repository_id))
    try:
        safe_repo_path(path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    file = await get_file(repository_id, path)
    if not file:
        raise HTTPException(status_code=404, detail="File is not in the analyzed sample.")
    return file


@router.get("/api/v1/repositories/{repository_id}/chats")
async def chats(repository_id: str):
    _repo_or_404(await get_repository(repository_id))
    return {"items": await list_chats(repository_id)}


@router.get("/api/v1/repositories/{repository_id}/chats/{chat_id}")
async def chat_detail(repository_id: str, chat_id: str):
    _repo_or_404(await get_repository(repository_id))
    chat = await get_chat(repository_id, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found.")
    return chat


@router.delete("/api/v1/repositories/{repository_id}/chats/{chat_id}")
async def chat_delete(repository_id: str, chat_id: str):
    _repo_or_404(await get_repository(repository_id))
    deleted = await delete_chat(repository_id, chat_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Chat not found.")
    return {"deleted": True}


@router.post("/api/v1/repositories/{repository_id}/chat")
async def chat(repository_id: str, req: ChatRequest, request: Request):
    settings = get_settings()
    limiter.check(f"chat:{client_ip(request)}", settings.chat_rate_limit, settings.chat_rate_window_seconds)
    repo = _repo_or_404(await get_repository(repository_id))
    if req.stream:
        prepared = await prepare_chat(repo, req.question, req.chat_id)
        provider = LLMProvider()

        async def events():
            if not settings.llm_configured:
                answer, uncertainty = fallback_answer(prepared["chunks"], req.question)
                await add_message(prepared["chat_id"], "assistant", answer, prepared["citations"], uncertainty)
                yield f"data: {json.dumps({'mode': 'fallback', 'delta': answer})}\n\n"
                yield f"data: {json.dumps({'done': True, 'chat_id': prepared['chat_id'], 'citations': prepared['citations'], 'uncertainty': uncertainty, 'mode': 'fallback'})}\n\n"
                return
            pieces: list[str] = []
            async for delta in provider.stream(prepared["messages"]):
                pieces.append(delta)
                yield f"data: {json.dumps({'delta': delta})}\n\n"
            answer = "".join(pieces).strip()
            if not answer:
                answer, uncertainty = fallback_answer(prepared["chunks"], req.question)
                await add_message(prepared["chat_id"], "assistant", answer, prepared["citations"], uncertainty)
                yield f"data: {json.dumps({'mode': 'fallback', 'delta': answer})}\n\n"
                yield f"data: {json.dumps({'done': True, 'chat_id': prepared['chat_id'], 'citations': prepared['citations'], 'uncertainty': uncertainty, 'mode': 'fallback'})}\n\n"
                return
            uncertainty = None
            await add_message(prepared["chat_id"], "assistant", answer, prepared["citations"], uncertainty)
            yield f"data: {json.dumps({'done': True, 'chat_id': prepared['chat_id'], 'citations': prepared['citations'], 'uncertainty': uncertainty, 'mode': 'llm'})}\n\n"

        return StreamingResponse(events(), media_type="text/event-stream")
    return await answer_question(repo, req.question, req.chat_id)
