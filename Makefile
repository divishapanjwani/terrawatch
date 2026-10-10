.PHONY: setup setup-backend setup-frontend demo test test-backend test-frontend eval lint format clean

PYTHON := python3.11
VENV := backend/venv
VENV_BIN := $(VENV)/bin

# One-time setup: backend venv + deps + TinyCD weights, frontend node_modules.
# OSCD training and the WorldPop raster are optional and skipped here (large
# downloads) -- see README.md "Optional: train Engine 2" / "Optional: population".
setup: setup-backend setup-frontend
	@echo ""
	@echo "Setup done. Run 'make demo' to start both servers with the Wayanad demo wired up."

setup-backend:
	$(PYTHON) -m venv $(VENV)
	$(VENV_BIN)/pip install --upgrade pip -q
	$(VENV_BIN)/pip install -r backend/requirements.txt -q
	mkdir -p backend/models/tinycd
	test -f backend/models/tinycd/levir_best.pth || \
		curl -sL -o backend/models/tinycd/levir_best.pth \
		https://github.com/AndreaCodegoni/Tiny_model_4_CD/raw/main/pretrained_models/levir_best.pth
	mkdir -p frontend/public/demo
	cp sample_data/wayanad/before.tif frontend/public/demo/wayanad_before.tif
	cp sample_data/wayanad/after.tif frontend/public/demo/wayanad_after.tif
	mkdir -p backend/data/wayanad
	cp sample_data/wayanad/before.tif backend/data/wayanad/before.tif
	cp sample_data/wayanad/after.tif backend/data/wayanad/after.tif

setup-frontend:
	cd frontend && npm install

# Starts backend (port 8000) and frontend (port 5173) together; Ctrl+C stops both.
demo:
	@echo "Backend:  http://127.0.0.1:8000"
	@echo "Frontend: http://localhost:5173  (click 'Load Wayanad demo' on the empty state)"
	@trap 'kill 0' EXIT; \
	( cd backend && venv/bin/uvicorn app.main:app --port 8000 ) & \
	( cd frontend && npm run dev ) & \
	wait

test: test-backend test-frontend

test-backend:
	cd backend && venv/bin/python -m pytest tests/ -v

test-frontend:
	cd frontend && npm run build

# Runs the full accuracy ablation (raw -> +morphology -> +false-alarm filter)
# for every engine/dataset combination that has its data downloaded.
# Needs LEVIR-CD (test split) and/or OSCD + a trained Engine 2 checkpoint --
# see docs/EVALUATION.md "Reproducing the numbers".
eval:
	cd backend && venv/bin/python scripts/evaluate.py levircd --ablation || true
	cd backend && venv/bin/python scripts/evaluate.py oscd --engine spectral --ablation || true
	cd backend && venv/bin/python scripts/evaluate.py oscd --engine engine2 --ablation || true

lint:
	cd backend && venv/bin/ruff check app scripts tests
	cd backend && venv/bin/black --check app scripts tests
	cd frontend && npm run format:check

format:
	cd backend && venv/bin/ruff check app scripts tests --fix
	cd backend && venv/bin/black app scripts tests
	cd frontend && npm run format

clean:
	rm -rf backend/data/analyses backend/data/uploads backend/data/terrawatch.db
	rm -rf frontend/dist
