cd "D:\desk top\agent\market-impact-agent-v2\agent-python"
.venv\Scripts\activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8010



git status
git add .
git commit -m "update project"
git push