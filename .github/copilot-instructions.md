# ETL DB2/CSV → MSSQL — Project Guidelines

## Architecture
- **Python 3.10+** ETL application running on Windows Server
- Source: DB2 LUW (ibm_db) + local CSV files
- Target: SQL Server 2016+ (SQLAlchemy + pyodbc)
- Web UI: Flask with Flask-Login authentication
- Scheduler: APScheduler (cron/interval/daily)
- Config: YAML per table (`config/tables/<name>.yaml`)
- Credentials: `.env` file encrypted with Fernet

## Project Structure
```
src/connectors/     # db2_connector, mssql_connector, csv_connector
src/etl/            # engine, loader, schema_manager, chunker, validator
src/scheduler/      # job_scheduler (APScheduler wrapper)
src/logging/        # etl_logger (DB-backed job logs)
src/config/         # config_loader, config_versioning
src/security/       # crypto (Fernet encrypt/decrypt)
src/web/            # Flask app, auth, routes, templates, static
config/             # app.yaml + tables/*.yaml
scripts/            # init_db.py
```

## Code Style
- Use `logging.getLogger(__name__)` for all modules
- Use context managers for database connections (`with connector.connect() as conn:`)
- All SQL queries must use **parameterized statements** (`:param_name`) — never f-string interpolation for user data
- Type hints for function signatures
- Docstrings for public classes and methods

## ETL Modes
- `insert_skip` — INSERT only new rows (skip if key exists)
- `upsert` — MERGE (UPDATE if key exists, INSERT if not)
- `delete_insert` — DELETE by rpt_dt period, then INSERT

## Key Patterns
- Composite primary keys: `[contract_id, rpt_dt]`, `[customer_id, rpt_dt]`
- rpt_dt column can be DATE, VARCHAR, or INT
- NULL key handling: configurable (`delete` / `skip` / `keep`)
- Chunking threshold: 100k rows, parallel workers max 4
- Connection pool: DB2 max 5, MSSQL max 10+5 overflow

## DB2 → MSSQL Type Mapping
| DB2 | MSSQL |
|-----|-------|
| VARCHAR(n) | NVARCHAR(n) |
| INTEGER | INT |
| DECIMAL(p,s) | DECIMAL(p,s) |
| TIMESTAMP | DATETIME2 |
| CLOB | NVARCHAR(MAX) |
| BLOB | VARBINARY(MAX) |

## Security
- Credentials in `.env` (encrypted with Fernet), never committed to git
- Web UI requires login/password
- Audit trail: Windows username logged with every ETL run
- OWASP: parameterized queries, CSRF protection, input validation

## Build & Run
```bash
pip install -r requirements.txt
python -m src.security.crypto generate-key    # Generate Fernet key
python -m src.security.crypto encrypt         # Encrypt .env passwords
python scripts/init_db.py                     # Init DB tables + admin user
python run.py                                 # Start web UI + scheduler
python run.py --run --table <name>            # Run ETL for one table
python run.py --dry-run --table <name>        # Dry-run (no insert)
```

## Testing
- Tests in `tests/` directory
- Run with `pytest` from project root

## Conventions
- Each table gets its own YAML config in `config/tables/`
- Schema drift: auto ALTER TABLE + warning log
- Config versioning: changes stored in MSSQL `etl_config_history`
- ETL logs: `etl_job_log` table in MSSQL target database
- All log tables auto-created on `scripts/init_db.py`
