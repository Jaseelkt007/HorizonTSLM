# Zurich EHL Time Series

Zurich hackathon time-series project.

## Setup

Install [`uv`](https://docs.astral.sh/uv/) and create the project environment:

```powershell
uv sync
```

Run Python commands inside the environment with `uv run`, for example:

```powershell
uv run python --version
```

Add runtime and development dependencies with:

```powershell
uv add pandas
uv add --dev pytest ruff
```

Commit `uv.lock` so every contributor uses the same dependency versions.
