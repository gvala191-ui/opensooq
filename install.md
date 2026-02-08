powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex

--------- (в консоли, открыть через проводник) ------------
uv venv .venv
.\.venv\Scripts\activate.bat
uv sync
playwright install
python parser.py