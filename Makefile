.PHONY: install dev frontend backend setup

setup: install frontend-install
	@mkdir -p data
	@cp -n .env.example .env 2>/dev/null || true
	@echo "✅ Setup complete. Edit .env with your keys."

install:
	cd backend && pip install -r requirements.txt

frontend-install:
	cd frontend && npm install

backend:
	cd backend && uvicorn main:app --reload --host 0.0.0.0 --port 8000

frontend:
	cd frontend && npm run dev

dev:
	@echo "Starting Megan..."
	@make backend & make frontend & wait
