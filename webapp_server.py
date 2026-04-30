"""
WebApp server — Railway web service uchun
PORT environment variable dan port oladi
"""
import os
import uvicorn
from webapp.app import app

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
