Hard-coded values in `gmail_stats.py` that could move to environment variables:

- `gmail_stats.py:43` `SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]`
- `gmail_stats.py:67` Log file path `gmail_stats.log`
- `gmail_stats.py:128,139,146,148` Credential/cache filenames `token.json`, `client_secret.json`
- `gmail_stats.py:261,311` Gmail list page size `500`
- `gmail_stats.py:372` `SAFE_BATCH_SIZE = 10`
- `gmail_stats.py:470-471,560-563,865,895,922,942` Fixed UI divider widths (`"=" * 50`, `"-" * 40`)
- `gmail_stats.py:516-519,956` Default serve port `8000` and host `127.0.0.1`
- `gmail_stats.py:499,777` Default export dir `.`
- `gmail_stats.py:953` `uvicorn` log level `"warning"`
- `gmail_stats.py:477` CLI description text
- `gmail_stats.py:488` Help text references “typically 5000”
- `gmail_stats.py:611` `"unlimited"` string in logging
