#!/bin/bash
echo '======================================'
echo '   Recruitment AI - Starting Up'
echo '======================================'

cd ~/recruitment_ai
source venv/bin/activate

echo 'Clearing ports...'
pkill -f 'uvicorn api:app' 2>/dev/null
pkill -f 'streamlit run' 2>/dev/null
pkill -f 'http.server 8082' 2>/dev/null
sleep 2

echo 'Starting API server...'
uvicorn api:app --host 127.0.0.1 --port 8000 > logs/api.log 2>&1 &

echo 'Waiting for API to be ready...'
for i in {1..20}; do
    if curl -s http://127.0.0.1:8000/api/v1/health > /dev/null 2>&1; then
        echo 'API is ready.'
        break
    fi
    sleep 1
done

echo 'Starting HTML dashboard...'
cd ~/recruitment_ai/dashboard && python3.11 -m http.server 8082 > /dev/null 2>&1 &
cd ~/recruitment_ai

echo 'Starting Streamlit UI...'
streamlit run ui/__init__.py --server.port 8501 --browser.gatherUsageStats false > logs/streamlit.log 2>&1 &

sleep 3
echo ''
echo '======================================'
echo '   All Systems Running'
echo '======================================'
echo '  Employer Dashboard : http://localhost:8501'
echo '  Analytics Dashboard: http://localhost:8082'
echo '  API Docs           : http://localhost:8000/docs'
echo '======================================'

open http://localhost:8501
open http://localhost:8082

wait
