"""FastAPI frontend for saved-account Instagram analyses."""

from __future__ import annotations

import logging
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Literal
from uuid import uuid4

import instaloader
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from instagram_analyzer.accounts import AccountStore
from instagram_analyzer.browser_auth import (
    BrowserAuthenticationError,
    SavedSessionExpiredError,
)
from instagram_analyzer.history import HistoryStore
from instagram_analyzer.service import AnalysisResult, run_saved_account_analysis


class AnalysisRequest(BaseModel):
    account_id: int = Field(gt=0)
    target_username: str = Field(min_length=1, max_length=200)
    analysis_type: Literal["non_followers"] = "non_followers"


@dataclass(slots=True)
class AnalysisJob:
    id: str
    account_id: int
    target_input: str
    status: str = "queued"
    stage: str = "queued"
    progress: int = 0
    message: str = "Waiting to start"
    error: str | None = None
    result: AnalysisResult | None = None
    lock: Lock = field(default_factory=Lock, repr=False)

    def update(self, stage: str, progress: int, message: str) -> None:
        with self.lock:
            self.status = "completed" if stage == "completed" else "running"
            self.stage = stage
            self.progress = max(0, min(100, progress))
            self.message = message


app = FastAPI(
    title="Instagram Analyzer API",
    version="1.0.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://localhost:8080"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)

account_store = AccountStore()
history_store = HistoryStore()
jobs: dict[str, AnalysisJob] = {}
jobs_lock = Lock()
executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="instagram-analysis")
logger = logging.getLogger(__name__)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/accounts")
def list_accounts() -> dict[str, list[dict[str, Any]]]:
    return {
        "accounts": [
            {
                "id": account.id,
                "username": account.username,
                "created_at": account.created_at,
                "last_used_at": account.last_used_at,
            }
            for account in account_store.list_accounts()
        ]
    }


@app.delete("/api/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(account_id: int) -> None:
    deleted = account_store.delete_account(account_id)
    if deleted is None:
        raise HTTPException(status_code=404, detail="Saved account was not found.")
    session_path = account_store.session_path(deleted)
    try:
        session_path.unlink(missing_ok=True)
    except OSError as error:
        raise HTTPException(
            status_code=500,
            detail="Account was removed, but its session file could not be deleted.",
        ) from error


@app.get("/api/analysis-options")
def analysis_options() -> dict[str, Any]:
    return {
        "analysis_types": [
            {
                "id": "non_followers",
                "label": "Non-followers",
                "description": "Accounts the target follows that do not follow back.",
            }
        ],
        "history_annotations": True,
        "reports": ["txt", "html"],
    }


@app.post("/api/analyses", status_code=status.HTTP_202_ACCEPTED)
def start_analysis(request: AnalysisRequest) -> dict[str, str]:
    if not any(
        account.id == request.account_id for account in account_store.list_accounts()
    ):
        raise HTTPException(status_code=404, detail="Saved account was not found.")

    job_id = uuid4().hex
    job = AnalysisJob(
        id=job_id,
        account_id=request.account_id,
        target_input=request.target_username,
    )
    with jobs_lock:
        jobs[job_id] = job
    executor.submit(_run_job, job)
    return {"id": job_id, "status": job.status}


@app.get("/api/analyses/{job_id}")
def analysis_status(job_id: str) -> dict[str, Any]:
    return _job_payload(_get_job(job_id), include_result=True)


@app.get("/api/analyses/{job_id}/result")
def analysis_result(job_id: str) -> dict[str, Any]:
    job = _get_job(job_id)
    with job.lock:
        if job.status == "failed":
            raise HTTPException(status_code=409, detail=job.error or "Analysis failed.")
        if job.result is None:
            raise HTTPException(status_code=409, detail="Analysis is not complete yet.")
        return _result_payload(job.id, job.result)


@app.post("/api/analyses/{job_id}/html-report")
def create_html_report(job_id: str) -> dict[str, str]:
    job = _get_job(job_id)
    with job.lock:
        if job.result is None:
            raise HTTPException(status_code=409, detail="Analysis is not complete yet.")
        return {
            "filename": job.result.html_report_path.name,
            "download_url": f"/api/analyses/{job.id}/html-report/download",
        }


@app.get("/api/analyses/{job_id}/html-report/download")
def download_html_report(job_id: str) -> FileResponse:
    job = _get_job(job_id)
    with job.lock:
        if job.result is None:
            raise HTTPException(status_code=409, detail="Analysis is not complete yet.")
        report_path = job.result.html_report_path.resolve()
    if not report_path.is_file():
        raise HTTPException(status_code=404, detail="HTML report file was not found.")
    return FileResponse(
        report_path,
        media_type="text/html; charset=utf-8",
        filename=report_path.name,
    )


def _run_job(job: AnalysisJob) -> None:
    try:
        result = run_saved_account_analysis(
            job.account_id,
            job.target_input,
            account_store=account_store,
            history_store=history_store,
            progress=job.update,
        )
    except Exception as error:  # The worker must always expose a terminal state.
        logger.exception("Analysis job %s failed", job.id)
        with job.lock:
            job.status = "failed"
            job.stage = "failed"
            job.message = "Analysis failed"
            job.error = _friendly_error(error)
        return
    with job.lock:
        job.result = result
        job.status = "completed"
        job.stage = "completed"
        job.progress = 100
        job.message = "Analysis complete"


def _get_job(job_id: str) -> AnalysisJob:
    with jobs_lock:
        job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Analysis was not found.")
    return job


def _job_payload(job: AnalysisJob, *, include_result: bool) -> dict[str, Any]:
    with job.lock:
        payload: dict[str, Any] = {
            "id": job.id,
            "status": job.status,
            "stage": job.stage,
            "progress": job.progress,
            "message": job.message,
            "error": job.error,
        }
        if include_result and job.result is not None:
            payload["result"] = _result_payload(job.id, job.result)
        return payload


def _result_payload(job_id: str, result: AnalysisResult) -> dict[str, Any]:
    all_accounts = [
        {
            "username": account.username,
            "previously_checked": account.previously_checked,
        }
        for account in result.accounts
    ]
    return {
        "id": job_id,
        "authenticated_username": result.authenticated_username,
        "target_username": result.target_username,
        "started_at": result.started_at.isoformat(),
        "completed_at": result.completed_at.isoformat(),
        "statistics": {
            "following": result.following_count,
            "followers": result.follower_count,
            "total_analyzed": result.total_analyzed,
            "previously_checked": result.previously_checked_count,
            "new": result.new_count,
        },
        "accounts": all_accounts,
        "new_accounts": [item for item in all_accounts if not item["previously_checked"]],
        "previously_checked_accounts": [
            item for item in all_accounts if item["previously_checked"]
        ],
        "txt_report": str(result.txt_report_path),
        "html_report": {
            "filename": result.html_report_path.name,
            "download_url": f"/api/analyses/{job_id}/html-report/download",
        },
    }


def _friendly_error(error: Exception) -> str:
    if isinstance(error, ValueError):
        return str(error)
    if isinstance(error, SavedSessionExpiredError):
        return "The saved Instagram session has expired. Refresh it through the CLI."
    if isinstance(error, BrowserAuthenticationError):
        return str(error) or "Saved Instagram authentication failed."
    if isinstance(error, instaloader.ProfileNotExistsException):
        return "Instagram profile was not found."
    if isinstance(error, instaloader.PrivateProfileNotFollowedException):
        return "This private profile is not accessible to the saved account."
    if isinstance(error, instaloader.LoginRequiredException):
        return "The saved Instagram session has expired. Refresh it through the CLI."
    if isinstance(error, instaloader.TooManyRequestsException):
        return "Instagram rate limit reached. Wait before trying again."
    if isinstance(error, instaloader.ConnectionException):
        return f"Instagram connection failed: {error}"
    if isinstance(error, instaloader.InstaloaderException):
        return f"Instagram request failed: {error}"
    if isinstance(error, sqlite3.Error):
        return f"Local database failure: {error}"
    return "Unexpected analysis failure. Check the backend logs for details."
