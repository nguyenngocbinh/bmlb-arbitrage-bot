"""FastAPI web dashboard for BMLB Arbitrage Bot."""
import json
import os
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from app.backtesting.analyzer import BacktestAnalyzer
from app.backtesting.recorder import DataRecorder
from app.backtesting.engine import BacktestEngine
from app.core.launch_profile import load_bot_profile, save_bot_profile
from app.persistence.database import DatabaseService


class BacktestRunRequest(BaseModel):
    """Request to run a backtest from a recorded orderbook session."""

    recording_session_id: int = Field(..., ge=1)
    initial_balance_usd: float = Field(1000, gt=0, le=10000000)
    profit_threshold_usd: float = Field(0, ge=0, le=1000000)
    profit_threshold_pct: float = Field(0, ge=0, le=100)
    slippage_bps: float = Field(0, ge=0, le=10000)
    cooldown_seconds: float = Field(0, ge=0, le=86400)


class BotProfileRequest(BaseModel):
    """Bot launch profile persisted by Settings."""

    mode: str
    renew_time: int = Field(..., ge=1)
    usdt_amount: float = Field(..., gt=0)
    exchanges: list[str]
    symbols: list[str]
    dry_run: bool = True
    no_recovery: bool = True


def create_app(
    db_service: Optional[DatabaseService] = None,
    data_recorder: Optional[DataRecorder] = None,
) -> FastAPI:
    """Create the FastAPI application."""
    app = FastAPI(
        title="BMLB Arbitrage Bot Dashboard",
        description="Dashboard for monitoring arbitrage trading",
        version="2.0.0",
    )

    templates_dir = os.path.join(os.path.dirname(__file__), "templates")
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    templates = Jinja2Templates(directory=templates_dir)
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    db = db_service or DatabaseService()
    recorder = data_recorder or DataRecorder()
    backtest_engine = BacktestEngine(data_recorder=recorder)

    @app.get("/", response_class=HTMLResponse)
    async def landing(request: Request):
        return templates.TemplateResponse(request, "landing.html", context={})

    @app.get("/getting-started", response_class=HTMLResponse)
    async def getting_started(request: Request):
        return templates.TemplateResponse(request, "getting_started.html", context={})

    @app.get("/settings", response_class=HTMLResponse)
    async def settings(request: Request):
        return templates.TemplateResponse(
            request, "settings.html", context={"profile": load_bot_profile()}
        )

    @app.get("/backtest", response_class=HTMLResponse)
    async def backtest(request: Request):
        return templates.TemplateResponse(
            request,
            "backtest.html",
            context={
                "recording_sessions": recorder.get_recording_sessions(),
                "backtest_runs": recorder.get_backtest_runs(limit=20),
            },
        )

    @app.get("/dashboard", response_class=HTMLResponse)
    async def dashboard(request: Request):
        stats = db.get_overall_stats()
        sessions = db.get_all_sessions(limit=10)
        recent_trades = db.get_all_trades(limit=8)
        daily_profit = db.get_daily_profit(days=30)
        hourly_profit = db.get_hourly_profit(days=1)
        latest_session = sessions[0] if sessions else None
        opportunities = (
            db.get_opportunities_by_session(latest_session["id"], limit=8)
            if latest_session
            else []
        )
        running_sessions = stats.get("running_sessions") or 0
        bot_status = "RUNNING" if running_sessions else "IDLE"
        tracked_exchanges = []
        if latest_session:
            tracked_exchanges = [
                x.strip()
                for x in (latest_session.get("exchanges") or "").split(",")
                if x.strip()
            ]
        return templates.TemplateResponse(
            request,
            "dashboard.html",
            context={
                "stats": stats,
                "sessions": sessions,
                "recent_trades": recent_trades,
                "daily_profit": daily_profit,
                "hourly_profit": hourly_profit,
                "opportunities": opportunities,
                "latest_session": latest_session,
                "bot_status": bot_status,
                "tracked_exchanges": tracked_exchanges,
            },
        )

    @app.get("/api/sessions")
    async def get_sessions(
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
        status: str = Query(None),
        symbol: str = Query(None),
    ):
        sessions = db.get_all_sessions(limit, offset, status, symbol)
        return {"success": True, "data": sessions, "count": len(sessions)}

    @app.get("/api/sessions/{session_id}")
    async def get_session(session_id: int):
        session = db.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"success": True, "data": session}

    @app.get("/api/trades")
    async def get_trades(
        limit: int = Query(100, ge=1, le=1000),
        offset: int = Query(0, ge=0),
        symbol: str = Query(None),
        buy_exchange: str = Query(None),
        sell_exchange: str = Query(None),
        start_date: str = Query(None),
        end_date: str = Query(None),
    ):
        trades = db.get_all_trades(
            limit, offset, symbol, buy_exchange, sell_exchange, start_date, end_date
        )
        return {"success": True, "data": trades, "count": len(trades)}

    @app.get("/api/sessions/{session_id}/trades")
    async def get_session_trades(
        session_id: int,
        limit: int = Query(100, ge=1, le=1000),
        offset: int = Query(0, ge=0),
    ):
        trades = db.get_trades_by_session(session_id, limit, offset)
        return {"success": True, "data": trades, "count": len(trades)}

    @app.get("/api/stats/overview")
    async def get_overview_stats():
        return {"success": True, "data": db.get_overall_stats()}

    @app.get("/api/stats/profit/daily")
    async def get_daily_profit(days: int = Query(30, ge=1, le=365)):
        return {"success": True, "data": db.get_daily_profit(days)}

    @app.get("/api/stats/profit/hourly")
    async def get_hourly_profit(
        session_id: int = Query(None), days: int = Query(7, ge=1, le=90)
    ):
        return {"success": True, "data": db.get_hourly_profit(session_id, days)}

    @app.get("/api/stats/profit/by-symbol")
    async def get_profit_by_symbol():
        return {"success": True, "data": db.get_profit_by_symbol()}

    @app.get("/api/stats/profit/by-exchange-pair")
    async def get_profit_by_exchange():
        return {"success": True, "data": db.get_profit_by_exchange_pair()}

    @app.get("/api/stats/exchange-performance")
    async def get_exchange_performance():
        return {"success": True, "data": db.get_exchange_performance()}

    @app.get("/api/stats/slippage")
    async def get_slippage_stats(session_id: int = Query(None)):
        return {"success": True, "data": db.get_slippage_stats(session_id)}

    @app.get("/api/stats/slippage/by-exchange")
    async def get_slippage_by_exchange(session_id: int = Query(None)):
        return {"success": True, "data": db.get_slippage_by_exchange(session_id)}

    @app.get("/api/errors")
    async def get_errors(
        session_id: int = Query(None),
        error_type: str = Query(None),
        limit: int = Query(100, ge=1, le=500),
    ):
        errors = db.get_errors(session_id, error_type, limit)
        return {"success": True, "data": errors, "count": len(errors)}

    @app.get("/api/settings/bot-profile")
    async def get_bot_profile():
        return {"success": True, "data": load_bot_profile()}

    @app.put("/api/settings/bot-profile")
    async def update_bot_profile(profile: BotProfileRequest):
        try:
            saved_profile = save_bot_profile(profile.model_dump())
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return {"success": True, "data": saved_profile}

    @app.get("/api/backtest/sessions")
    async def get_backtest_sessions():
        sessions = recorder.get_recording_sessions()
        return {"success": True, "data": sessions, "count": len(sessions)}

    @app.post("/api/backtest/run")
    async def run_backtest(request: BacktestRunRequest):
        recording_session = recorder.get_recording_session(request.recording_session_id)
        if not recording_session:
            raise HTTPException(status_code=404, detail="Recording session not found")
        exchanges = json.loads(recording_session["exchanges"])
        if len(exchanges) < 2:
            raise HTTPException(status_code=422, detail="Backtest requires at least two exchanges")
        result = backtest_engine.run(
            symbol=recording_session["symbol"],
            exchanges=exchanges,
            initial_balance_usd=request.initial_balance_usd,
            profit_threshold_usd=request.profit_threshold_usd,
            profit_threshold_pct=request.profit_threshold_pct,
            slippage_bps=request.slippage_bps,
            cooldown_seconds=request.cooldown_seconds,
            recording_session_id=request.recording_session_id,
        )
        if result.start_time is None:
            raise HTTPException(status_code=422, detail="Recording session has no snapshots")
        analysis = BacktestAnalyzer.analyze(result)
        run_id = recorder.save_backtest_result(request.recording_session_id, result, analysis)
        return {"success": True, "data": recorder.get_backtest_run(run_id)}

    @app.get("/api/backtest/results")
    async def get_backtest_results(limit: int = Query(50, ge=1, le=500)):
        runs = recorder.get_backtest_runs(limit)
        return {"success": True, "data": runs, "count": len(runs)}

    @app.get("/api/backtest/results/{run_id}")
    async def get_backtest_result(run_id: int):
        run = recorder.get_backtest_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Backtest result not found")
        run["trades"] = recorder.get_backtest_trades(run_id)
        return {"success": True, "data": run}

    @app.get("/api/health")
    async def health_check():
        return {"status": "ok", "service": "arbitrage-bot-dashboard"}

    return app


app = create_app()
