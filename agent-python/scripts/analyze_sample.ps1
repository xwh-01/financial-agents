Invoke-RestMethod `
  -Uri "http://localhost:8001/agent/analyze" `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"title":"Elon Musk says Tesla robotaxi launch is expected soon","content":"Tesla robotaxi plan may accelerate and affect investor sentiment.","source":"news","published_at":"2026-05-15T10:00:00Z"}'